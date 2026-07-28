from fastapi import APIRouter, Depends, status

from app.dependencies.platform_auth import get_current_platform_admin
from app.models.platform_admin import PlatformAdmin
from app.modules.tenants.schemas import (
    TenantProvisionRequest,
    TenantProvisionResponse,
    TenantSummary,
    TenantUpdateRequest,
)
from app.modules.tenants.service import create_tenant, list_tenants, update_tenant

router = APIRouter(prefix="/api/v1/tenants", tags=["Tenants"])


@router.post("", response_model=TenantProvisionResponse, status_code=status.HTTP_201_CREATED)
def provision_tenant(
    payload: TenantProvisionRequest,
    _current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantProvisionResponse:
    result = create_tenant(
        tenant_id=payload.tenant_id,
        tenant_name=payload.tenant_name,
        admin_email=payload.admin_email,
        admin_password=payload.admin_password,
        doctors=[doc.model_dump() for doc in payload.doctors],
    )
    return TenantProvisionResponse(**result)


@router.get("", response_model=list[TenantSummary])
def get_tenants(
    _current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> list[TenantSummary]:
    return [TenantSummary(**t) for t in list_tenants()]


@router.patch("/{tenant_id}", response_model=TenantSummary)
def patch_tenant(
    tenant_id: str,
    payload: TenantUpdateRequest,
    _current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantSummary:
    result = update_tenant(tenant_id, name=payload.name, is_active=payload.is_active)
    return TenantSummary(**result)
