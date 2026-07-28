from datetime import datetime

from pydantic import BaseModel, Field


class DoctorSeed(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    specialty: str = Field(min_length=1, max_length=255)
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)


class TenantProvisionRequest(BaseModel):
    tenant_id: str = Field(min_length=1, pattern=r"^[a-z0-9_]+$")
    tenant_name: str = Field(min_length=1, max_length=255)
    admin_email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    admin_password: str = Field(min_length=8, max_length=128)
    doctors: list[DoctorSeed] = Field(default_factory=list, max_length=50)


class TenantProvisionResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    admin_email: str
    db_name: str
    doctors_created: int
    message: str


class TenantSummary(BaseModel):
    tenant_id: str
    name: str
    country: str
    is_active: bool
    created_at: datetime


class TenantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None
