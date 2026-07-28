from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.db import get_db
from app.models.tenant import Tenant, User, UserRole
from app.schemas.user import TenantSelfRead, UserDirectoryEntry, UserRead, UserUpdate
from app.services.user_service import deactivate_user as svc_deactivate_user
from app.services.user_service import reactivate_user as svc_reactivate_user
from app.services.user_service import update_user as svc_update_user

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("", response_model=list[UserDirectoryEntry])
def list_users(
    role: UserRole | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Directorio minimo de usuarios del tenant (id, nombre, rol) para resolver
    nombres en pantallas como Agenda o el historial del paciente. Sin datos
    sensibles (sin email/telefono)."""
    query = db.query(User).filter(User.tenant_id == current_user.tenant_id, User.deleted_at.is_(None), User.is_active.is_(True))
    if role:
        query = query.filter(User.role == role)
    return query.order_by(User.full_name.asc()).all()


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: UUID,
    data: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.clinic_admin)),
):
    return svc_update_user(db, user_id.bytes, current_user.tenant_id, data, current_user.id)


@router.patch("/{user_id}/deactivate", response_model=UserRead)
def deactivate_user(
    user_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.clinic_admin)),
):
    return svc_deactivate_user(db, user_id.bytes, current_user.tenant_id, current_user.id)


@router.patch("/{user_id}/reactivate", response_model=UserRead)
def reactivate_user(
    user_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.clinic_admin)),
):
    return svc_reactivate_user(db, user_id.bytes, current_user.tenant_id, current_user.id)


tenant_router = APIRouter(prefix="/api/v1/tenant", tags=["Users"])


@tenant_router.get("/me", response_model=TenantSelfRead)
def get_my_tenant(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Nombre/pais de la clinica del usuario autenticado -- a diferencia de
    /api/v1/tenants (solo platform-admin, lista todas las clinicas), este
    endpoint expone unicamente el propio tenant, para pantallas como el login
    o una factura que necesitan mostrar el nombre real de la clinica."""
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    return TenantSelfRead(tenant_id=current_user.tenant_id, name=tenant.name if tenant else current_user.tenant_id, country=tenant.country if tenant else None)
