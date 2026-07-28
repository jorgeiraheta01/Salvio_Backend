from datetime import datetime
from uuid import UUID

from pydantic import Field, SecretStr

from app.models.tenant import UserRole
from app.schemas.common import ORMModel, StrippedStringMixin, TimestampMixin


class UserBase(StrippedStringMixin, ORMModel):
    tenant_id: str = Field(min_length=1, max_length=50)
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    full_name: str = Field(min_length=2, max_length=255)
    role: UserRole
    is_active: bool = True


class UserCreate(UserBase):
    password: SecretStr = Field(min_length=8, max_length=128)


class UserUpdate(StrippedStringMixin, ORMModel):
    email: str | None = Field(default=None, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None
    password: SecretStr | None = Field(default=None, min_length=8, max_length=128)


class UserRead(UserBase, TimestampMixin):
    id: UUID
    deleted_at: datetime | None = None


class LoginRequest(ORMModel):
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: SecretStr = Field(min_length=1, max_length=128)


class TokenPair(ORMModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class LoginResponse(TokenPair):
    requires_2fa: bool = False
    temp_token: str | None = None
    user: UserRead | None = None


class TwoFAVerifyRequest(ORMModel):
    otp_code: str = Field(min_length=4, max_length=10, pattern=r"^[0-9]+$")
    temp_token: str = Field(min_length=20)


class TwoFAVerifyResponse(TokenPair):
    user: UserRead


class RefreshTokenRequest(ORMModel):
    refresh_token: str = Field(min_length=20)


class RefreshTokenResponse(ORMModel):
    access_token: str
    token_type: str = "bearer"


class LogoutRequest(ORMModel):
    refresh_token: str = Field(min_length=20)


class PasswordResetRequest(ORMModel):
    tenant_id: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9_]+$")
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class PasswordResetConfirm(ORMModel):
    reset_token: str = Field(min_length=20)
    new_password: SecretStr = Field(min_length=8, max_length=128)


class OtpTokenSmsCreate(ORMModel):
    user_id: UUID
    phone_number: str = Field(min_length=8, max_length=30)
    otp_code_hash: str = Field(min_length=32, max_length=64)
    expires_at: datetime


class OtpTokenSmsRead(OtpTokenSmsCreate):
    id: UUID
    used: bool
    created_at: datetime


class RevokedTokenCreate(ORMModel):
    jti: str = Field(min_length=8, max_length=255)
    user_id: UUID
    expires_at: datetime


class RevokedTokenRead(RevokedTokenCreate):
    id: UUID
    created_at: datetime
