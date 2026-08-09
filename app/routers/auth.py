from datetime import datetime, timedelta, timezone
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import jwt
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.rate_limit import limiter
from app.database import DATABASE_URL, _reject_if_session_invalidated, get_tenant_engine
from app.modules.tenants.service import _validate_tenant_id
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
from app.models.tenant import RevokedToken, Tenant, TenantStatus, User
from app.routers._utils import audit_mutation, client_ip, commit_or_409
from app.utils.audit import log_audit
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
PASSWORD_RESET_EXPIRE_MINUTES = 30
logger = logging.getLogger("salvio.auth")

# H-15: 2FA para usuarios de clinica quedo fuera del alcance de la
# auditoria (a diferencia del owner, donde SI es obligatorio -- ver Grupo A
# / app/utils/totp.py) porque un usuario de clinica no puede tumbar la
# plataforma entera. Antes esto era un `requires_2fa = False` hardcodeado
# en medio del login, indistinguible de un TODO olvidado. Ahora es una
# decision explicita via env var -- sigue apagado por defecto, pero queda
# documentado que es una eleccion, no un descuido, y activable sin tocar
# codigo si el negocio decide requerirlo.
TENANT_2FA_ENABLED = os.getenv("TENANT_2FA_ENABLED", "false").lower() == "true"


class LoginRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9_]+$")
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: SecretStr = Field(min_length=1, max_length=128)


def _tenant_db_name(tenant_id: str) -> str:
    return f"salvio_{tenant_id}"


def _server_database_url() -> str:
    if not DATABASE_URL:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="DATABASE_URL no esta configurada.")
    return make_url(DATABASE_URL).set(database=None).render_as_string(hide_password=False)


def _tenant_database_url(tenant_id: str) -> str:
    if not DATABASE_URL:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="DATABASE_URL no esta configurada.")
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo la busqueda de la clinica: {exc}") from exc
    finally:
        engine.dispose()


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
def login(request: Request, data: LoginRequest):
    tenant_id = _validate_tenant_id(data.tenant_id)
    _ensure_tenant_database_exists(tenant_id)

    tenant_engine = create_engine(_tenant_database_url(tenant_id), pool_pre_ping=True)
    tenant_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = tenant_session_factory()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant is not None and tenant.status != TenantStatus.active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Esta clinica ha sido desactivada.")

        user = (
            db.query(User)
            .filter(User.tenant_id == tenant_id, User.email == data.email, User.deleted_at.is_(None))
            .first()
        )
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas.")
        if not user.is_active or not verify_password(data.password.get_secret_value(), user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas.")

        if TENANT_2FA_ENABLED:
            temp_token = create_token(user, token_type="2fa", expires_delta=__import__("datetime").timedelta(minutes=5))
            return LoginResponse(access_token="", refresh_token=None, requires_2fa=True, temp_token=temp_token)

        user.last_login_at = datetime.now(timezone.utc)
        log_audit(
            db,
            tenant_id=tenant_id,
            user_id=user.id,
            action="LOGIN",
            table_name="users",
            record_id=user.id,
            ip_address=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()

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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de 2FA invalido.")
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido.")
    db = _tenant_session(tenant_id)
    try:
        row = (
            db.query(User, Tenant.status)
            .outerjoin(Tenant, Tenant.id == User.tenant_id)
            .filter(User.id == __import__("uuid").UUID(payload["sub"]).bytes, User.tenant_id == tenant_id, User.deleted_at.is_(None))
            .first()
        )
        if not row or not row[0].is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado o inactivo.")
        user, tenant_status = row
        if tenant_status is not None and tenant_status != TenantStatus.active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Esta clinica ha sido desactivada.")
        user.last_login_at = datetime.now(timezone.utc)
        db.commit()
        return TwoFAVerifyResponse(access_token=create_access_token(user), refresh_token=create_refresh_token(user), user=user)
    finally:
        db.close()


@router.post("/refresh", response_model=RefreshTokenResponse)
def refresh_token(data: RefreshTokenRequest):
    payload = decode_token(data.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de actualizacion invalido.")
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido.")
    db = _tenant_session(tenant_id)
    try:
        # H-09: a clinic deactivated after the refresh token was issued must not
        # be able to keep minting new access tokens. Single joined query, same
        # tenant connection already open for the user lookup.
        row = (
            db.query(User, Tenant.status)
            .outerjoin(Tenant, Tenant.id == User.tenant_id)
            .filter(User.id == __import__("uuid").UUID(payload["sub"]).bytes, User.tenant_id == tenant_id, User.deleted_at.is_(None))
            .first()
        )
        if not row or not row[0].is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado o inactivo.")
        user, tenant_status = row
        if tenant_status is not None and tenant_status != TenantStatus.active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Esta clinica ha sido desactivada.")
        _reject_if_session_invalidated(db, tenant_id, payload)
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
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El token de actualizacion no tiene jti.")
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de restablecimiento invalido o expirado.")
    tenant_id = payload.get("tenant_id")
    user_id = payload.get("sub")
    if not tenant_id or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido.")

    jti = payload.get("jti")
    db = _tenant_session(tenant_id)
    try:
        if jti and db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Este enlace de restablecimiento ya fue utilizado.")
        user = db.query(User).filter(User.id == __import__("uuid").UUID(user_id).bytes, User.tenant_id == tenant_id, User.deleted_at.is_(None)).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de restablecimiento invalido o expirado.")
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
