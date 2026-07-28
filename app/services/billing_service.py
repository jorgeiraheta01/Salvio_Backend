from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.billing import Billing, BillingItem, BillingStatus, Payment, PaymentStatus
from app.models.patient import Patient
from app.schemas.billing import BillingCreate, BillingUpdate, PaymentCreate
from app.services._utils import audit, commit_or_409, data_for_model, model_to_dict, new_uuid_bytes, not_found

# H-03: unica transicion permitida es hacia adelante -- una vez void/refunded
# no hay vuelta atras (evita reabrir una factura ya cerrada contablemente).
BILLING_ALLOWED_TRANSITIONS = {
    BillingStatus.pending: {BillingStatus.paid, BillingStatus.void},
    BillingStatus.paid: {BillingStatus.refunded},
    BillingStatus.void: set(),
    BillingStatus.refunded: set(),
}


def create_billing(db: Session, tenant_id: str, data: BillingCreate, user_id: bytes) -> Billing:
    # H-06: antes solo la FK protegia contra un patient_id inexistente, y ni
    # eso contra uno archivado (soft-delete no rompe la FK).
    patient = db.query(Patient).filter(Patient.id == data.patient_id.bytes, Patient.tenant_id == tenant_id, Patient.deleted_at.is_(None)).first()
    if not patient:
        raise not_found("Patient not found.")

    total_billing = Decimal("0")
    for item in data.items:
        item_total = (item.quantity * item.unit_price) - item.discount_amount + item.tax_amount
        item.total_amount = item_total
        total_billing += item_total
    billing = Billing(**data_for_model(data, Billing, exclude={"items"}, tenant_id=tenant_id))
    billing.id = new_uuid_bytes()
    billing.amount = total_billing
    if not billing.due_date:
        billing.due_date = datetime.now(timezone.utc) + timedelta(days=30)
    if not billing.invoice_number:
        existing_count = db.query(func.count(Billing.id)).filter(Billing.tenant_id == tenant_id).scalar() or 0
        billing.invoice_number = str(existing_count + 1)
    db.add(billing)
    db.flush()
    for item in data.items:
        payload = data_for_model(item, BillingItem, tenant_id=tenant_id)
        payload["id"] = new_uuid_bytes()
        payload["billing_id"] = billing.id
        db.add(BillingItem(**payload))
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="billing", record_id=billing.id, new_values=model_to_dict(billing))
    commit_or_409(db)
    db.refresh(billing)
    return billing


def register_payment(db: Session, billing_id: bytes, tenant_id: str, data: PaymentCreate, user_id: bytes) -> tuple[Billing, Payment]:
    billing = db.query(Billing).filter(Billing.id == billing_id, Billing.tenant_id == tenant_id).first()
    if not billing:
        raise not_found("Billing not found.")
    if billing.status == BillingStatus.void:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot pay a voided billing")
    old_billing = model_to_dict(billing)
    payment = Payment(**data_for_model(data, Payment, tenant_id=tenant_id))
    payment.id = new_uuid_bytes()
    payment.billing_id = billing_id
    payment.status = PaymentStatus.completed
    db.add(payment)
    db.flush()
    paid_total = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.billing_id == billing_id, Payment.tenant_id == tenant_id, Payment.status == PaymentStatus.completed)
        .scalar()
    )
    billing_updated = False
    if Decimal(str(paid_total)) >= billing.amount:
        billing.status = BillingStatus.paid
        billing.payment_date = datetime.now(timezone.utc)
        billing_updated = True
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="payments", record_id=payment.id, new_values=model_to_dict(payment))
    if billing_updated:
        audit(db, user_id=user_id, tenant_id=tenant_id, action="UPDATE", table_name="billing", record_id=billing.id, old_values=old_billing, new_values=model_to_dict(billing))
    commit_or_409(db)
    db.refresh(billing)
    db.refresh(payment)
    return billing, payment


def update_billing(db: Session, billing_id: bytes, tenant_id: str, data: BillingUpdate, user_id: bytes) -> Billing:
    billing = db.query(Billing).filter(Billing.id == billing_id, Billing.tenant_id == tenant_id).first()
    if not billing:
        raise not_found("Billing not found.")

    if data.status is not None and data.status != billing.status:
        if data.status not in BILLING_ALLOWED_TRANSITIONS[billing.status]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot transition billing from '{billing.status.value}' to '{data.status.value}'",
            )

    old = model_to_dict(billing)
    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(billing, field, value)
    audit(db, user_id=user_id, tenant_id=tenant_id, action="UPDATE", table_name="billing", record_id=billing.id, old_values=old, new_values=model_to_dict(billing))
    commit_or_409(db)
    db.refresh(billing)
    return billing
