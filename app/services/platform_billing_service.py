from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.platform_billing import ChargeStatus, PlatformCharge
from app.modules.tenants.service import ensure_tenant_exists
from app.services._utils import commit_or_409


def _to_dict(charge: PlatformCharge) -> dict:
    return {
        "id": UUID(bytes=charge.id),
        "invoice_number": charge.invoice_number,
        "tenant_id": charge.tenant_id,
        "period_label": charge.period_label,
        "amount": charge.amount,
        "currency": charge.currency,
        "status": charge.status,
        "due_date": charge.due_date,
        "paid_at": charge.paid_at,
        "notes": charge.notes,
        "created_at": charge.created_at,
    }


def create_charge(db: Session, admin_id: bytes, tenant_id: str, period_label: str, amount: Decimal, due_date, notes: str | None) -> dict:
    safe_tenant_id = ensure_tenant_exists(tenant_id)
    # Correlativo por clinica (no global): siguiente numero dentro de esta
    # tenant_id. Una race teorica entre dos creaciones simultaneas para la
    # misma clinica queda cubierta por el UNIQUE (tenant_id, invoice_number)
    # -- fallaria con 409 via commit_or_409-like catch, no duplicaria numero.
    last_number = db.query(func.max(PlatformCharge.invoice_number)).filter(PlatformCharge.tenant_id == safe_tenant_id).scalar()
    charge = PlatformCharge(
        id=uuid4().bytes,
        invoice_number=(last_number or 0) + 1,
        tenant_id=safe_tenant_id,
        period_label=period_label,
        amount=amount,
        currency="USD",
        status=ChargeStatus.pending,
        due_date=due_date,
        notes=notes,
        created_by=admin_id,
    )
    db.add(charge)
    commit_or_409(db, detail="Ya existe un cobro con ese numero de factura para esta clinica, intenta de nuevo.")
    db.refresh(charge)
    return _to_dict(charge)


def list_charges(db: Session, tenant_id: str | None) -> dict:
    query = db.query(PlatformCharge)
    if tenant_id:
        query = query.filter(PlatformCharge.tenant_id == tenant_id)
    rows = query.order_by(PlatformCharge.created_at.desc()).all()

    totals = {"pending": Decimal("0"), "paid": Decimal("0"), "void": Decimal("0")}
    for row in rows:
        key = row.status.value if hasattr(row.status, "value") else str(row.status)
        totals[key] += row.amount

    return {"charges": [_to_dict(r) for r in rows], "totals": totals}


def get_charge(db: Session, charge_id: UUID) -> PlatformCharge:
    charge = db.query(PlatformCharge).filter(PlatformCharge.id == charge_id.bytes).first()
    if charge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Charge not found.")
    return charge


def update_charge_status(db: Session, charge_id: UUID, new_status: ChargeStatus) -> dict:
    charge = db.query(PlatformCharge).filter(PlatformCharge.id == charge_id.bytes).first()
    if charge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Charge not found.")
    charge.status = new_status
    charge.paid_at = datetime.now(timezone.utc) if new_status == ChargeStatus.paid else None
    db.commit()
    db.refresh(charge)
    return _to_dict(charge)
