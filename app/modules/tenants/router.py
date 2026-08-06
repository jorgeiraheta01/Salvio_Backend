from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import sessionmaker

from app.database import get_control_engine
from app.dependencies.auth import get_current_user
from app.dependencies.platform_auth import get_current_platform_admin
from app.models.platform_admin import PlatformAdmin
from app.models.tenant import User
from app.modules.tenants.schemas import (
    StaffCreateRequest,
    StaffPasswordResetResponse,
    StaffSummary,
    StaffUpdateRequest,
    TenantDashboardResponse,
    TenantModuleSummary,
    TenantModuleUpdateRequest,
    TenantProvisionRequest,
    TenantProvisionResponse,
    TenantSummary,
    TenantTableStats,
    TenantTechnicalStats,
    TenantUpdateRequest,
)
from app.modules.tenants.service import (
    create_tenant,
    create_tenant_staff,
    delete_tenant_staff,
    force_staff_logout,
    force_tenant_admin_logout,
    force_tenant_logout,
    get_tenant_admin,
    list_tenant_staff,
    list_tenant_modules,
    list_tenants,
    reset_tenant_admin_password,
    reset_tenant_staff_password,
    set_tenant_module,
    tenant_dashboard_stats,
    tenant_table_breakdown,
    tenant_technical_stats,
    update_tenant,
    update_tenant_staff,
)
from app.schemas.common import MessageResponse
from app.utils.control_audit import log_control_audit

router = APIRouter(prefix="/api/v1/tenants", tags=["Tenants"])

# Lectura para usuarios de la propia clinica (no el dueno de la plataforma):
# consultar el estado de sus propios modulos, para poder avisarles en su
# dashboard si el dueno les apago alguno (ver Resumen/dashboard del
# frontend). Mismo patron que platform_settings.public_router.
public_router = APIRouter(prefix="/api/v1/tenant", tags=["Tenant Self"])


@public_router.get("/modules", response_model=list[TenantModuleSummary])
def get_own_tenant_modules(current_user: User = Depends(get_current_user)) -> list[TenantModuleSummary]:
    return [TenantModuleSummary(**m) for m in list_tenant_modules(current_user.tenant_id)]


def _log(admin: PlatformAdmin, request: Request, **kwargs) -> None:
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())
    db = session_factory()
    try:
        log_control_audit(
            db,
            admin_id=admin.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            **kwargs,
        )
        db.commit()
    finally:
        db.close()


@router.post("", response_model=TenantProvisionResponse, status_code=status.HTTP_201_CREATED)
def provision_tenant(
    payload: TenantProvisionRequest,
    request: Request,
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantProvisionResponse:
    result = create_tenant(
        tenant_id=payload.tenant_id,
        tenant_name=payload.tenant_name,
        admin_email=payload.admin_email,
        admin_password=payload.admin_password,
        doctors=[doc.model_dump() for doc in payload.doctors],
    )
    _log(
        current_admin,
        request,
        action="create_tenant",
        table_name="tenants",
        tenant_id=result["tenant_id"],
        new_values={"tenant_name": result["tenant_name"], "admin_email": result["admin_email"], "doctors_created": result["doctors_created"]},
    )
    return TenantProvisionResponse(**result)


@router.get("/dashboard", response_model=TenantDashboardResponse)
def get_tenant_dashboard(
    _current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantDashboardResponse:
    return TenantDashboardResponse(**tenant_dashboard_stats())


@router.get("/technical-metrics", response_model=list[TenantTechnicalStats])
def get_tenant_technical_metrics(
    _current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> list[TenantTechnicalStats]:
    return [TenantTechnicalStats(**t) for t in tenant_technical_stats()]


@router.get("/{tenant_id}/database-tables", response_model=list[TenantTableStats])
def get_tenant_database_tables(
    tenant_id: str,
    _current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> list[TenantTableStats]:
    return [TenantTableStats(**t) for t in tenant_table_breakdown(tenant_id)]


@router.get("", response_model=list[TenantSummary])
def get_tenants(
    include_archived: bool = Query(default=False),
    _current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> list[TenantSummary]:
    return [TenantSummary(**t) for t in list_tenants(include_archived=include_archived)]


@router.patch("/{tenant_id}", response_model=TenantSummary)
def patch_tenant(
    tenant_id: str,
    payload: TenantUpdateRequest,
    request: Request,
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantSummary:
    result = update_tenant(
        tenant_id,
        name=payload.name,
        status=payload.status,
        billing_contact_name=payload.billing_contact_name,
        billing_contact_phone=payload.billing_contact_phone,
    )
    _log(
        current_admin,
        request,
        action="update_tenant",
        table_name="tenants",
        tenant_id=tenant_id,
        new_values={
            "name": payload.name,
            "status": payload.status.value if payload.status else None,
            "billing_contact_name": payload.billing_contact_name,
            "billing_contact_phone": payload.billing_contact_phone,
        },
    )
    return TenantSummary(**result)


@router.post("/{tenant_id}/force-logout", response_model=MessageResponse)
def post_force_logout(
    tenant_id: str,
    request: Request,
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> MessageResponse:
    force_tenant_logout(tenant_id)
    _log(current_admin, request, action="force_logout", table_name="tenants", tenant_id=tenant_id)
    return MessageResponse(message="OK")


@router.get("/{tenant_id}/modules", response_model=list[TenantModuleSummary])
def get_tenant_modules(
    tenant_id: str,
    _current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> list[TenantModuleSummary]:
    return [TenantModuleSummary(**m) for m in list_tenant_modules(tenant_id)]


@router.patch("/{tenant_id}/modules/{module_key}", response_model=TenantModuleSummary)
def patch_tenant_module(
    tenant_id: str,
    module_key: str,
    payload: TenantModuleUpdateRequest,
    request: Request,
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantModuleSummary:
    result = set_tenant_module(tenant_id, module_key, payload.enabled)
    _log(
        current_admin,
        request,
        action="update_tenant_module",
        table_name="tenant_module_flags",
        tenant_id=tenant_id,
        new_values={"module_key": module_key, "enabled": payload.enabled},
    )
    return TenantModuleSummary(**result)


@router.get("/{tenant_id}/admin", response_model=StaffSummary)
def get_tenant_admin_route(
    tenant_id: str,
    _current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> StaffSummary:
    return StaffSummary(**get_tenant_admin(tenant_id))


@router.post("/{tenant_id}/admin/reset-password", response_model=StaffPasswordResetResponse)
def post_reset_admin_password(
    tenant_id: str,
    request: Request,
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> StaffPasswordResetResponse:
    result = reset_tenant_admin_password(tenant_id)
    _log(
        current_admin,
        request,
        action="reset_admin_password",
        table_name="users",
        tenant_id=tenant_id,
    )
    return StaffPasswordResetResponse(**result)


@router.post("/{tenant_id}/admin/force-logout", response_model=MessageResponse)
def post_force_admin_logout(
    tenant_id: str,
    request: Request,
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> MessageResponse:
    force_tenant_admin_logout(tenant_id)
    _log(current_admin, request, action="force_admin_logout", table_name="users", tenant_id=tenant_id)
    return MessageResponse(message="OK")


@router.post("/{tenant_id}/staff/{user_id}/reset-password", response_model=StaffPasswordResetResponse)
def post_reset_staff_password(
    tenant_id: str,
    user_id: str,
    request: Request,
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> StaffPasswordResetResponse:
    result = reset_tenant_staff_password(tenant_id, user_id)
    _log(
        current_admin,
        request,
        action="reset_staff_password",
        table_name="users",
        tenant_id=tenant_id,
        new_values={"user_id": user_id},
    )
    return StaffPasswordResetResponse(**result)


@router.post("/{tenant_id}/staff/{user_id}/force-logout", response_model=MessageResponse)
def post_force_staff_logout(
    tenant_id: str,
    user_id: str,
    request: Request,
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> MessageResponse:
    force_staff_logout(tenant_id, user_id)
    _log(
        current_admin,
        request,
        action="force_staff_logout",
        table_name="users",
        tenant_id=tenant_id,
        new_values={"user_id": user_id},
    )
    return MessageResponse(message="OK")


@router.get("/{tenant_id}/staff", response_model=list[StaffSummary])
def get_tenant_staff(
    tenant_id: str,
    role: str | None = Query(default=None),
    _current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> list[StaffSummary]:
    return [StaffSummary(**member) for member in list_tenant_staff(tenant_id, role)]


@router.post("/{tenant_id}/staff", response_model=StaffSummary, status_code=status.HTTP_201_CREATED)
def post_tenant_staff(
    tenant_id: str,
    payload: StaffCreateRequest,
    request: Request,
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> StaffSummary:
    result = create_tenant_staff(tenant_id, payload.model_dump())
    _log(
        current_admin,
        request,
        action="create_staff",
        table_name="users",
        tenant_id=tenant_id,
        new_values={"email": result["email"], "full_name": result["full_name"], "role": result["role"]},
    )
    return StaffSummary(**result)


@router.patch("/{tenant_id}/staff/{user_id}", response_model=StaffSummary)
def patch_tenant_staff(
    tenant_id: str,
    user_id: str,
    payload: StaffUpdateRequest,
    request: Request,
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> StaffSummary:
    result = update_tenant_staff(tenant_id, user_id, payload.model_dump(exclude_unset=True))
    _log(
        current_admin,
        request,
        action="update_staff",
        table_name="users",
        tenant_id=tenant_id,
        new_values={"user_id": user_id, **payload.model_dump(exclude_unset=True)},
    )
    return StaffSummary(**result)


@router.delete("/{tenant_id}/staff/{user_id}", response_model=MessageResponse)
def delete_tenant_staff_route(
    tenant_id: str,
    user_id: str,
    request: Request,
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> MessageResponse:
    delete_tenant_staff(tenant_id, user_id)
    _log(
        current_admin,
        request,
        action="deactivate_staff",
        table_name="users",
        tenant_id=tenant_id,
        new_values={"user_id": user_id},
    )
    return MessageResponse(message="OK")
