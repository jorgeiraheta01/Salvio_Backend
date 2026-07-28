import enum

from sqlalchemy import BINARY, Boolean, Column, DateTime, Enum as SQLEnum, String, Text
from sqlalchemy.sql import func

from app.models.platform_admin import ControlBase


class AnnouncementSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class MaintenanceMode(ControlBase):
    """Fila unica (siempre la misma id) -- no hay "varios modos de
    mantenimiento", solo un interruptor global de la plataforma."""

    __tablename__ = "maintenance_mode"

    id = Column(BINARY(16), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    message = Column(Text, nullable=True)
    enabled_at = Column(DateTime, nullable=True)
    enabled_by = Column(BINARY(16), nullable=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class PlatformAnnouncement(ControlBase):
    __tablename__ = "platform_announcements"

    id = Column(BINARY(16), primary_key=True)
    message = Column(Text, nullable=False)
    severity = Column(SQLEnum(AnnouncementSeverity), nullable=False, default=AnnouncementSeverity.info)
    active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BINARY(16), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class PlatformFeatureFlag(ControlBase):
    __tablename__ = "feature_flags"

    id = Column(BINARY(16), primary_key=True)
    key = Column(String(100), nullable=False, unique=True)
    enabled = Column(Boolean, nullable=False, default=False)
    description = Column(Text, nullable=True)
