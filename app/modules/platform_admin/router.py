from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from jose import jwt
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.orm import sessionmaker

from app.database import get_control_engine
from app.dependencies.auth import ALGORITHM, SECRET_KEY, verify_password
from app.models.platform_admin import PlatformAdmin

router = APIRouter(prefix="/api/v1/platform-admin", tags=["Platform Admin"])

PLATFORM_ADMIN_TOKEN_EXPIRE_HOURS = 8


class PlatformAdminLoginRequest(BaseModel):
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: SecretStr = Field(min_length=1, max_length=128)


class PlatformAdminLoginResponse(BaseModel):
    access_token: str


@router.post("/login", response_model=PlatformAdminLoginResponse)
def platform_admin_login(data: PlatformAdminLoginRequest) -> PlatformAdminLoginResponse:
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())
    db = session_factory()
    try:
        admin = db.query(PlatformAdmin).filter(PlatformAdmin.email == data.email.strip().lower()).first()
        if not admin or not admin.is_active or not verify_password(data.password.get_secret_value(), admin.hashed_password):
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
        return PlatformAdminLoginResponse(access_token=token)
    finally:
        db.close()
