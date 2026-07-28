from datetime import datetime, timedelta, timezone
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import jwt
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.database import DATABASE_URL, get_tenant_engine
from app.dependencies.auth import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    create_refresh_token,
    create_token,
    decode_token,
    get_current_user,
    verify_password,
)
from app.dependencies.db import get_db
from app.models.tenant import RevokedToken, Tenant, User
from app.routers._utils import audit_mutation, commit_or_409
from app.schemas.auth import (
    LoginResponse,
    LogoutRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    TwoFAVerifyRequest,
    TwoFAVerifyResponse,
)
from app.schemas.common import MessageResponse
from app.utils.password import pwd_context
from uuid import uuid4

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
TENANT_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")
PASSWORD_RESET_EXPIRE_MINUTES = 30
logger = logging.getLogger("salvio.auth")


class LoginRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9_]+$")
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: SecretStr = Field(min_length=1, max_length=128)


def _validate_tenant_id(tenant_id: str) -> str:
    value = tenant_id.strip()
    if not value or not TENANT_ID_PATTERN.fullmatch(value):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid tenant_id.")
    return value


def _tenant_db_name(tenant_id: str) -> str:
    return f"salvio_{tenant_id}"


def _server_database_url() -> str:
    if not DATABASE_URL:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="DATABASE_URL is not configured.")
    return make_url(DATABASE_URL).set(database=None).render_as_string(hide_password=False)


def _tenant_database_url(tenant_id: str) -> str:
    if not DATABASE_URL:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="DATABASE_URL is not configured.")
    return make_url(DATABASE_URL).set(database=_tenant_db_name(tenant_id)).render_as_string(hide_password=False)


def _ensure_tenant_database_exists(tenant_id: str) -> None:
    engine = create_engine(_server_database_url(), pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            exists = connection.execute(text("SHOW DATABASES LIKE :db_name"), {"db_name": _tenant_db_name(tenant_id)}).scalar()
            if not exists:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant no existe")
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Tenant lookup failed: {exc}") from exc
    finally:
        engine.dispose()


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest):
    tenant_id = _validate_tenant_id(data.tenant_id)
    _ensure_tenant_database_exists(tenant_id)

    tenant_engine = create_engine(_tenant_database_url(tenant_id), pool_pre_ping=True)
    tenant_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = tenant_session_factory()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant is not None and not tenant.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This clinic has been deactivated.")

        user = (
            db.query(User)
            .filter(User.tenant_id == tenant_id, User.email == data.email, User.deleted_at.is_(None))
            .first()
        )
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
        if not user.is_active or not verify_password(data.password.get_secret_value(), user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

        requires_2fa = False
        if requires_2fa:
            temp_token = create_token(user, token_type="2fa", expires_delta=__import__("datetime").timedelta(minutes=5))
            return LoginResponse(access_token="", refresh_token=None, requires_2fa=True, temp_token=temp_token)

        return LoginResponse(
            access_token=create_access_token(user),
            refresh_token=create_refresh_token(user),
            requires_2fa=False,
        )
    finally:
        db.close()
        tenant_engine.dispose()


def _tenant_session(tenant_id: str) -> Session:
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_tenant_engine(tenant_id))
    return session_factory()


@router.post("/2fa/verify", response_model=TwoFAVerifyResponse)
def verify_2fa(data: TwoFAVerifyRequest):
    payload = decode_token(data.temp_token)
    if payload.get("type") != "2fa":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid 2FA token.")
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    db = _tenant_session(tenant_id)
    try:
        user = db.query(User).filter(User.id == __import__("uuid").UUID(payload["sub"]).bytes, User.tenant_id == tenant_id, User.deleted_at.is_(None)).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive.")
        return TwoFAVerifyResponse(access_token=create_access_token(user), refresh_token=create_refresh_token(user), user=user)
    finally:
        db.close()


@router.post("/refresh", response_model=RefreshTokenResponse)
def refresh_token(data: RefreshTokenRequest):
    payload = decode_token(data.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    db = _tenant_session(tenant_id)
    try:
        user = db.query(User).filter(User.id == __import__("uuid").UUID(payload["sub"]).bytes, User.tenant_id == tenant_id, User.deleted_at.is_(None)).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive.")
        return RefreshTokenResponse(access_token=create_access_token(user))
    finally:
        db.close()


@router.post("/logout", response_model=MessageResponse)
def logout(
    data: LogoutRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = jwt.decode(data.refresh_token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Refresh token has no jti.")
    if not db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        db.add(
            RevokedToken(
                id=uuid4().bytes,
                jti=jti,
                user_id=current_user.id,
                expires_at=datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc),
            )
        )
    audit_mutation(db, request, current_user, action="logout", table_name="revoked_tokens", record_id=current_user.id)
    commit_or_409(db)
    return MessageResponse(message="OK")


@router.post("/password-reset/request", response_model=MessageResponse)
def request_password_reset(data: PasswordResetRequest):
    tenant_id = _validate_tenant_id(data.tenant_id)
    generic_response = MessageResponse(message="If the account exists, a password reset link has been sent.")
    try:
        _ensure_tenant_database_exists(tenant_id)
    except HTTPException:
        # Do not disclose whether the tenant exists.
        return generic_response

    tenant_engine = create_engine(_tenant_database_url(tenant_id), pool_pre_ping=True)
    tenant_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = tenant_session_factory()
    try:
        user = (
            db.query(User)
            .filter(User.tenant_id == tenant_id, User.email == data.email, User.deleted_at.is_(None))
            .first()
        )
        if user is not None and user.is_active:
            reset_token = create_token(user, token_type="password_reset", expires_delta=timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES))
            # No email/SMS provider is wired up yet (see .env.example) -- logging the link
            # server-side is a deliberate stand-in so the flow is fully testable end-to-end
            # locally. Before production launch this must be replaced with a real delivery
            # channel (email or the existing WhatsApp Cloud API integration).
            logger.warning(
                "Password reset requested for %s (tenant=%s). Reset token (valid %s min): %s",
                data.email,
                tenant_id,
                PASSWORD_RESET_EXPIRE_MINUTES,
                reset_token,
            )
        return generic_response
    finally:
        db.close()
        tenant_engine.dispose()


@router.post("/password-reset/confirm", response_model=MessageResponse)
def confirm_password_reset(data: PasswordResetConfirm):
    payload = decode_token(data.reset_token)
    if payload.get("type") != "password_reset":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired reset token.")
    tenant_id = payload.get("tenant_id")
    user_id = payload.get("sub")
    if not tenant_id or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")

    jti = payload.get("jti")
    db = _tenant_session(tenant_id)
    try:
        if jti and db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This reset link has already been used.")
        user = db.query(User).filter(User.id == __import__("uuid").UUID(user_id).bytes, User.tenant_id == tenant_id, User.deleted_at.is_(None)).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired reset token.")
        user.hashed_password = pwd_context.hash(data.new_password.get_secret_value())
        db.add(
            RevokedToken(
                id=uuid4().bytes,
                jti=payload.get("jti"),
                user_id=user.id,
                expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            )
        )
        commit_or_409(db)
        return MessageResponse(message="Password updated successfully.")
    finally:
        db.close()
