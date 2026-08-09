from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.tenant import TenantStatus


class DoctorSeed(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    specialty: str = Field(min_length=1, max_length=255)
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)


class TenantModuleSummary(BaseModel):
    module_key: str
    label: str
    enabled: bool


class TenantModuleUpdateRequest(BaseModel):
    enabled: bool


class StaffSummary(BaseModel):
    id: UUID
    full_name: str
    role: str
    specialty: str
    email: str
    is_active: bool


class StaffCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    role: str
    specialty: str = Field(default="", max_length=255)
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)


class StaffUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    specialty: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    is_active: bool | None = None


class StaffPasswordResetResponse(BaseModel):
    id: UUID
    email: str
    new_password: str


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
    status: TenantStatus
    created_at: datetime
    billing_contact_name: str | None = None
    billing_contact_phone: str | None = None


class TenantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: TenantStatus | None = None
    billing_contact_name: str | None = Field(default=None, max_length=255)
    billing_contact_phone: str | None = Field(default=None, max_length=50)


class TenantDashboardEntry(BaseModel):
    tenant_id: str
    name: str
    status: TenantStatus
    patients_count: int
    appointments_count: int
    encounters_count: int
    billing_pending: float
    billing_paid: float
    staff_count: int
    last_activity_at: datetime | None
    prescriptions_count: int
    lab_orders_count: int
    appointments_completed: int
    appointments_cancelled: int
    modules_active: int
    modules_total: int


class TenantDashboardTotals(BaseModel):
    patients: int
    appointments: int
    encounters: int
    billing_pending: float
    billing_paid: float
    staff: int
    prescriptions: int
    lab_orders: int
    appointments_completed: int
    appointments_cancelled: int


class TenantDashboardResponse(BaseModel):
    tenants: list[TenantDashboardEntry]
    totals: TenantDashboardTotals


class TenantTechnicalStats(BaseModel):
    tenant_id: str
    table_count: int
    size_mb: float
    approx_rows: int
    last_updated: datetime | None


class TenantTableStats(BaseModel):
    table_name: str
    approx_rows: int
    size_mb: float
    last_updated: datetime | None


class TenantLoginActivityEntry(BaseModel):
    ip_address: str
    last_seen: datetime
    login_count: int
    users: list[str]
