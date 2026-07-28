from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.db import get_db
from app.models.billing import Billing, BillingItem, BillingStatus, Payment
from app.models.tenant import User, UserRole
from app.routers._utils import audit_mutation, commit_or_409, data_for_create, data_for_model, get_by_id_or_404, model_to_dict, uuid_bytes
from app.schemas.billing import BillingCreate, BillingDetail, BillingRead, BillingUpdate, PaymentCreate, PaymentRead
from app.schemas.common import PaginatedResponse
from app.services.billing_service import create_billing as svc_create_billing
from app.services.billing_service import register_payment as svc_register_payment
from app.services.billing_service import update_billing as svc_update_billing

router = APIRouter(prefix="/api/v1/billing", tags=["Billing"])
BILLING_ROLES = (UserRole.clinic_admin, UserRole.accountant, UserRole.receptionist)


@router.post("", response_model=BillingRead, status_code=status.HTTP_201_CREATED)
def create_billing(
    data: BillingCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*BILLING_ROLES)),
):
    return svc_create_billing(db, current_user.tenant_id, data, current_user.id)


@router.get("", response_model=PaginatedResponse[BillingRead])
def list_billing(
    patient_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Billing).filter(Billing.tenant_id == current_user.tenant_id)
    if patient_id:
        query = query.filter(Billing.patient_id == uuid_bytes(patient_id))
    total = query.count()
    data = query.order_by(Billing.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return {"data": data, "total": total, "page": page, "limit": limit}


@router.get("/{billing_id}", response_model=BillingDetail)
def get_billing(billing_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    billing = get_by_id_or_404(db, Billing, billing_id, current_user.tenant_id)
    data = model_to_dict(billing)
    data["items"] = db.query(BillingItem).filter(BillingItem.billing_id == billing.id, BillingItem.tenant_id == current_user.tenant_id).all()
    data["payments"] = db.query(Payment).filter(Payment.billing_id == billing.id, Payment.tenant_id == current_user.tenant_id).all()
    return data


@router.patch("/{billing_id}", response_model=BillingRead)
def update_billing(
    billing_id: UUID,
    data: BillingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*BILLING_ROLES)),
):
    return svc_update_billing(db, billing_id.bytes, current_user.tenant_id, data, current_user.id)


@router.post("/{billing_id}/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def create_payment(
    billing_id: UUID,
    data: PaymentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*BILLING_ROLES)),
):
    _billing, payment = svc_register_payment(db, billing_id.bytes, current_user.tenant_id, data, current_user.id)
    return payment
