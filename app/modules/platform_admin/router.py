from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.orm import sessionmaker

from app.database import get_control_engine
from app.dependencies.auth import ALGORITHM, SECRET_KEY, decode_token, verify_password
from app.dependencies.platform_auth import get_current_platform_admin, get_platform_admin_credentials
from app.models.platform_admin import ControlRevokedToken, PlatformAdmin
from app.schemas.common import MessageResponse
from app.utils.control_audit import log_control_audit

router = APIRouter(prefix="/api/v1/platform-admin", tags=["Platform Admin"])

PLATFORM_ADMIN_TOKEN_EXPIRE_HOURS = 8


class PlatformAdminLoginRequest(BaseModel):
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: SecretStr = Field(min_length=1, max_length=128)


class PlatformAdminLoginResponse(BaseModel):
    access_token: str


@router.post("/login", response_model=PlatformAdminLoginResponse)
def platform_admin_login(data: PlatformAdminLoginRequest, request: Request) -> PlatformAdminLoginResponse:
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())
    db = session_factory()
    try:
        admin = db.query(PlatformAdmin).filter(PlatformAdmin.email == data.email.strip().lower()).first()
        if not admin or not admin.is_active or not verify_password(data.password.get_secret_value(), admin.hashed_password):
            # Tambien se audita el intento fallido -- login del owner es una
            # cuenta de alto impacto, sus intentos fallidos importan tanto
            # como sus exitos.
            log_control_audit(
                db,
                admin_id=admin.id if admin else None,
                action="login_failed",
                table_name="platform_admins",
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                new_values={"email": data.email.strip().lower()},
            )
            db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

        admin_id = str(UUID(bytes=admin.id))
        expires_at = datetime.now(timezone.utc) + timedelta(hours=PLATFORM_ADMIN_TOKEN_EXPIRE_HOURS)
        payload = {
            "sub": admin_id,
            "type": "platform_admin",
            "exp": expires_at,
            "jti": f"{admin_id}:platform_admin:{int(expires_at.timestamp())}",
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        log_control_audit(
            db,
            admin_id=admin.id,
            action="login",
            table_name="platform_admins",
            record_id=admin.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        return PlatformAdminLoginResponse(access_token=token)
    finally:
        db.close()


@router.post("/logout", response_model=MessageResponse)
def platform_admin_logout(
    request: Request,
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
    credentials: HTTPAuthorizationCredentials = Depends(get_platform_admin_credentials),
) -> MessageResponse:
    payload = decode_token(credentials.credentials)
    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Token has no jti.")

    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())
    db = session_factory()
    try:
        if not db.query(ControlRevokedToken).filter(ControlRevokedToken.jti == jti).first():
            db.add(
                ControlRevokedToken(
                    id=uuid4().bytes,
                    jti=jti,
                    admin_id=current_admin.id,
                    expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                )
            )
        log_control_audit(
            db,
            admin_id=current_admin.id,
            action="logout",
            table_name="platform_admins",
            record_id=current_admin.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        return MessageResponse(message="OK")
    finally:
        db.close()
