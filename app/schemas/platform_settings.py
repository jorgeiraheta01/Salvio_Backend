from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.models.platform_settings import AnnouncementSeverity
from app.schemas.common import ORMModel


class MaintenanceModeRead(ORMModel):
    enabled: bool
    message: str | None = None
    enabled_at: datetime | None = None


class MaintenanceModeUpdate(ORMModel):
    enabled: bool
    message: str | None = Field(default=None, max_length=2000)


class AnnouncementCreate(ORMModel):
    message: str = Field(min_length=1, max_length=2000)
    severity: AnnouncementSeverity = AnnouncementSeverity.info


class AnnouncementUpdate(ORMModel):
    message: str | None = Field(default=None, min_length=1, max_length=2000)
    severity: AnnouncementSeverity | None = None
    active: bool | None = None


class AnnouncementRead(ORMModel):
    id: UUID
    message: str
    severity: AnnouncementSeverity
    active: bool
    created_at: datetime


class FeatureFlagCreate(ORMModel):
    key: str = Field(min_length=1, max_length=100)
    enabled: bool = False
    description: str | None = Field(default=None, max_length=1000)


class FeatureFlagUpdate(ORMModel):
    enabled: bool | None = None
    description: str | None = Field(default=None, max_length=1000)


class FeatureFlagRead(ORMModel):
    id: UUID
    key: str
    enabled: bool
    description: str | None = None
