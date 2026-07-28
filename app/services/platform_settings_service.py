from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.platform_settings import MaintenanceMode, PlatformAnnouncement, PlatformFeatureFlag

# Fila unica de maintenance_mode -- id fijo para no tener que resolverla por
# ningun otro criterio (siempre hay a lo sumo una fila).
_MAINTENANCE_ROW_ID = UUID("00000000-0000-0000-0000-000000000001").bytes


def get_maintenance_mode(db: Session) -> MaintenanceMode:
    row = db.query(MaintenanceMode).filter(MaintenanceMode.id == _MAINTENANCE_ROW_ID).first()
    if not row:
        row = MaintenanceMode(id=_MAINTENANCE_ROW_ID, enabled=False)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def set_maintenance_mode(db: Session, *, enabled: bool, message: str | None, admin_id: bytes) -> MaintenanceMode:
    row = get_maintenance_mode(db)
    row.enabled = enabled
    row.message = message
    row.enabled_at = datetime.now(timezone.utc) if enabled else None
    row.enabled_by = admin_id if enabled else None
    db.commit()
    db.refresh(row)
    return row


def list_announcements(db: Session, *, only_active: bool = False) -> list[PlatformAnnouncement]:
    query = db.query(PlatformAnnouncement)
    if only_active:
        query = query.filter(PlatformAnnouncement.active.is_(True))
    return query.order_by(PlatformAnnouncement.created_at.desc()).all()


def create_announcement(db: Session, *, message: str, severity, admin_id: bytes) -> PlatformAnnouncement:
    item = PlatformAnnouncement(id=uuid4().bytes, message=message, severity=severity, active=True, created_by=admin_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_announcement(db: Session, announcement_id: bytes, *, message: str | None, severity, active: bool | None) -> PlatformAnnouncement | None:
    item = db.query(PlatformAnnouncement).filter(PlatformAnnouncement.id == announcement_id).first()
    if not item:
        return None
    if message is not None:
        item.message = message
    if severity is not None:
        item.severity = severity
    if active is not None:
        item.active = active
    db.commit()
    db.refresh(item)
    return item


def list_feature_flags(db: Session) -> list[PlatformFeatureFlag]:
    return db.query(PlatformFeatureFlag).order_by(PlatformFeatureFlag.key).all()


def create_feature_flag(db: Session, *, key: str, enabled: bool, description: str | None) -> PlatformFeatureFlag:
    item = PlatformFeatureFlag(id=uuid4().bytes, key=key, enabled=enabled, description=description)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_feature_flag(db: Session, flag_id: bytes, *, enabled: bool | None, description: str | None) -> PlatformFeatureFlag | None:
    item = db.query(PlatformFeatureFlag).filter(PlatformFeatureFlag.id == flag_id).first()
    if not item:
        return None
    if enabled is not None:
        item.enabled = enabled
    if description is not None:
        item.description = description
    db.commit()
    db.refresh(item)
    return item
