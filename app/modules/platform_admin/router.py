from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from jose import jwt
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.orm import sessionmaker

from app.database import get_control_engine
from app.dependencies.auth import ALGORITHM, SECRET_KEY, verify_password
from app.models.platform_admin import PlatformAdmin
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
