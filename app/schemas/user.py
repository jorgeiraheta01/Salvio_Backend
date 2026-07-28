from uuid import UUID

from app.models.tenant import UserRole
from app.schemas.common import ORMModel


class UserDirectoryEntry(ORMModel):
    id: UUID
    full_name: str
    role: UserRole
    specialty: str | None = None


class TenantSelfRead(ORMModel):
    tenant_id: str
    name: str
    country: str | None = None
