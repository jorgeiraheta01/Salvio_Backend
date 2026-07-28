from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_control_engine
from app.dependencies.auth import get_current_user
from app.dependencies.platform_auth import get_current_platform_admin
from app.models.platform_admin import PlatformAdmin
from app.models.tenant import User
from app.schemas.platform_settings import (
    AnnouncementCreate,
    AnnouncementRead,
    AnnouncementUpdate,
    FeatureFlagCreate,
    FeatureFlagRead,
    FeatureFlagUpdate,
    MaintenanceModeRead,
    MaintenanceModeUpdate,
)
from app.services.platform_settings_service import (
    create_announcement as svc_create_announcement,
    create_feature_flag as svc_create_feature_flag,
    get_maintenance_mode as svc_get_maintenance_mode,
    list_announcements as svc_list_announcements,
    list_feature_flags as svc_list_feature_flags,
    set_maintenance_mode as svc_set_maintenance_mode,
    update_announcement as svc_update_announcement,
    update_feature_flag as svc_update_feature_flag,
)
from app.utils.control_audit import log_control_audit

router = APIRouter(prefix="/api/v1/platform-admin", tags=["Platform Settings"])
public_router = APIRouter(prefix="/api/v1", tags=["Platform Settings"])


def _control_db() -> Session:
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())
    return session_factory()


def _log(db: Session, admin: PlatformAdmin, request: Request, **kwargs) -> None:
    log_control_audit(
        db,
        admin_id=admin.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        **kwargs,
    )
    db.commit()


@router.get("/maintenance-mode", response_model=MaintenanceModeRead)
def get_maintenance_mode(current_admin: PlatformAdmin = Depends(get_current_platform_admin)):
    db = _control_db()
    try:
        # Serializar mientras la sesion sigue abierta -- si se devuelve el
        # objeto ORM crudo, FastAPI lo serializa DESPUES de que el `finally`
        # ya cerro la sesion (DetachedInstanceError al leer sus atributos).
        return MaintenanceModeRead.model_validate(svc_get_maintenance_mode(db))
    finally:
        db.close()


@router.patch("/maintenance-mode", response_model=MaintenanceModeRead)
def update_maintenance_mode(
    data: MaintenanceModeUpdate,
    request: Request,
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
):
    db = _control_db()
    try:
        result = svc_set_maintenance_mode(db, enabled=data.enabled, message=data.message, admin_id=current_admin.id)
        response = MaintenanceModeRead.model_validate(result)
        _log(db, current_admin, request, action="maintenance_mode_update", table_name="maintenance_mode", new_values={"enabled": data.enabled, "message": data.message})
        return response
    finally:
        db.close()


@router.get("/announcements", response_model=list[AnnouncementRead])
def list_announcements(current_admin: PlatformAdmin = Depends(get_current_platform_admin)):
    db = _control_db()
    try:
        return [AnnouncementRead.model_validate(a) for a in svc_list_announcements(db)]
    finally:
        db.close()


@router.post("/announcements", response_model=AnnouncementRead, status_code=201)
def create_announcement(data: AnnouncementCreate, request: Request, current_admin: PlatformAdmin = Depends(get_current_platform_admin)):
    db = _control_db()
    try:
        result = svc_create_announcement(db, message=data.message, severity=data.severity, admin_id=current_admin.id)
        response = AnnouncementRead.model_validate(result)
        _log(db, current_admin, request, action="announcement_create", table_name="platform_announcements", record_id=result.id, new_values={"message": data.message, "severity": data.severity.value})
        return response
    finally:
        db.close()


@router.patch("/announcements/{announcement_id}", response_model=AnnouncementRead)
def update_announcement(announcement_id: UUID, data: AnnouncementUpdate, request: Request, current_admin: PlatformAdmin = Depends(get_current_platform_admin)):
    db = _control_db()
    try:
        result = svc_update_announcement(db, announcement_id.bytes, message=data.message, severity=data.severity, active=data.active)
        if not result:
            raise HTTPException(status_code=404, detail="Announcement not found.")
        response = AnnouncementRead.model_validate(result)
        _log(db, current_admin, request, action="announcement_update", table_name="platform_announcements", record_id=announcement_id.bytes, new_values=data.model_dump(exclude_unset=True))
        return response
    finally:
        db.close()


@router.get("/feature-flags", response_model=list[FeatureFlagRead])
def list_feature_flags_admin(current_admin: PlatformAdmin = Depends(get_current_platform_admin)):
    db = _control_db()
    try:
        return [FeatureFlagRead.model_validate(f) for f in svc_list_feature_flags(db)]
    finally:
        db.close()


@router.post("/feature-flags", response_model=FeatureFlagRead, status_code=201)
def create_feature_flag(data: FeatureFlagCreate, request: Request, current_admin: PlatformAdmin = Depends(get_current_platform_admin)):
    db = _control_db()
    try:
        result = svc_create_feature_flag(db, key=data.key, enabled=data.enabled, description=data.description)
        response = FeatureFlagRead.model_validate(result)
        _log(db, current_admin, request, action="feature_flag_create", table_name="feature_flags", record_id=result.id, new_values={"key": data.key, "enabled": data.enabled})
        return response
    finally:
        db.close()


@router.patch("/feature-flags/{flag_id}", response_model=FeatureFlagRead)
def update_feature_flag(flag_id: UUID, data: FeatureFlagUpdate, request: Request, current_admin: PlatformAdmin = Depends(get_current_platform_admin)):
    db = _control_db()
    try:
        result = svc_update_feature_flag(db, flag_id.bytes, enabled=data.enabled, description=data.description)
        if not result:
            raise HTTPException(status_code=404, detail="Feature flag not found.")
        response = FeatureFlagRead.model_validate(result)
        _log(db, current_admin, request, action="feature_flag_update", table_name="feature_flags", record_id=flag_id.bytes, new_values=data.model_dump(exclude_unset=True))
        return response
    finally:
        db.close()


# --- Lectura para usuarios de clinica (no owner) -- enforcement de feature
# flags queda deliberadamente solo en frontend por ahora, segun lo aprobado.


@public_router.get("/announcements/active", response_model=list[AnnouncementRead])
def list_active_announcements(current_user: User = Depends(get_current_user)):
    db = _control_db()
    try:
        return [AnnouncementRead.model_validate(a) for a in svc_list_announcements(db, only_active=True)]
    finally:
        db.close()


@public_router.get("/feature-flags", response_model=list[FeatureFlagRead])
def list_feature_flags_tenant(current_user: User = Depends(get_current_user)):
    db = _control_db()
    try:
        return [FeatureFlagRead.model_validate(f) for f in svc_list_feature_flags(db)]
    finally:
        db.close()
