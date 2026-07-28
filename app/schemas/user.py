from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.models.tenant import UserRole
from app.schemas.common import ORMModel, StrippedStringMixin


class UserDirectoryEntry(ORMModel):
    id: UUID
    full_name: str
    role: UserRole
    specialty: str | None = None


class UserUpdate(StrippedStringMixin, ORMModel):
    # Deliberadamente sin email/hashed_password/tenant_id -- cambiar
    # credenciales de acceso es un flujo distinto (reset de password), fuera
    # de alcance de este PATCH de datos de perfil.
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    specialty: str | None = Field(default=None, max_length=255)
    role: UserRole | None = None


class UserRead(ORMModel):
    id: UUID
    tenant_id: str
    email: str
    full_name: str
    role: UserRole
    specialty: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


class TenantSelfRead(ORMModel):
    tenant_id: str
    name: str
    country: str | None = None
