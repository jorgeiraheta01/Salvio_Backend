from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import sessionmaker

from app.database import get_control_engine
from app.dependencies.platform_auth import get_current_platform_admin
from app.models.platform_admin import PlatformAdmin
from app.modules.tenants.service import get_tenant_billing_info
from app.schemas.platform_billing import (
    PlatformChargeCreate,
    PlatformChargeRead,
    PlatformChargesResponse,
    PlatformChargeUpdate,
)
from app.services.invoice_pdf_service import generate_invoice_pdf
from app.services.platform_billing_service import create_charge, get_charge, list_charges, update_charge_status
from app.utils.control_audit import log_control_audit

router = APIRouter(prefix="/api/v1/platform-admin/billing", tags=["Platform Billing"])


def _db():
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())
    return session_factory()


def _log(admin: PlatformAdmin, request: Request, db, **kwargs) -> None:
    log_control_audit(
        db,
        admin_id=admin.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        **kwargs,
    )
    db.commit()


@router.get("", response_model=PlatformChargesResponse)
def get_charges(
    tenant_id: str | None = Query(default=None),
    _current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> PlatformChargesResponse:
    db = _db()
    try:
        return PlatformChargesResponse(**list_charges(db, tenant_id))
    finally:
        db.close()


@router.post("", response_model=PlatformChargeRead, status_code=201)
def post_charge(
    payload: PlatformChargeCreate,
    request: Request,
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> PlatformChargeRead:
    db = _db()
    try:
        result = create_charge(db, current_admin.id, payload.tenant_id, payload.period_label, payload.amount, payload.due_date, payload.notes)
        _log(
            current_admin,
            request,
            db,
            action="create_platform_charge",
            table_name="platform_charges",
            tenant_id=payload.tenant_id,
            new_values={"period_label": payload.period_label, "amount": str(payload.amount)},
        )
        return PlatformChargeRead(**result)
    finally:
        db.close()


@router.get("/{charge_id}/invoice.pdf")
def get_charge_invoice_pdf(
    charge_id: UUID,
    _current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> Response:
    db = _db()
    try:
        charge = get_charge(db, charge_id)
        tenant = get_tenant_billing_info(charge.tenant_id)
        pdf_bytes = generate_invoice_pdf(
            charge,
            tenant_name=tenant["name"],
            billing_contact_name=tenant["billing_contact_name"],
            billing_contact_phone=tenant["billing_contact_phone"],
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="factura-{charge.invoice_number}-{charge.tenant_id}.pdf"'},
        )
    finally:
        db.close()


@router.patch("/{charge_id}", response_model=PlatformChargeRead)
def patch_charge(
    charge_id: UUID,
    payload: PlatformChargeUpdate,
    request: Request,
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> PlatformChargeRead:
    db = _db()
    try:
        result = update_charge_status(db, charge_id, payload.status)
        _log(
            current_admin,
            request,
            db,
            action="update_platform_charge_status",
            table_name="platform_charges",
            record_id=charge_id.bytes,
            new_values={"status": payload.status.value},
        )
        return PlatformChargeRead(**result)
    finally:
        db.close()
