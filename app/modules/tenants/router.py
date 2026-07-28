from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import sessionmaker

from app.database import get_control_engine
from app.dependencies.platform_auth import get_current_platform_admin
from app.models.platform_admin import PlatformAdmin
from app.modules.tenants.schemas import (
    TenantDashboardResponse,
    TenantProvisionRequest,
    TenantProvisionResponse,
    TenantSummary,
    TenantUpdateRequest,
)
from app.modules.tenants.service import create_tenant, list_tenants, tenant_dashboard_stats, update_tenant
from app.utils.control_audit import log_control_audit

router = APIRouter(prefix="/api/v1/tenants", tags=["Tenants"])


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
    result = update_tenant(tenant_id, name=payload.name, status=payload.status)
    _log(
        current_admin,
        request,
        action="update_tenant",
        table_name="tenants",
        tenant_id=tenant_id,
        new_values={"name": payload.name, "status": payload.status.value if payload.status else None},
    )
    return TenantSummary(**result)
