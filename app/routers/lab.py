from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.db import get_db
from app.dependencies.module_gate import require_module
from app.models.lab import LabOrder, LabOrderItem, LabResult
from app.models.tenant import User, UserRole
from app.routers._utils import audit_mutation, commit_or_409, data_for_create, data_for_model, get_by_id_or_404, model_to_dict, uuid_bytes
from app.schemas.lab import LabOrderCreate, LabOrderDetail, LabOrderRead, LabOrderUpdate, LabResultCreate, LabResultRead
from app.services.lab_service import create_lab_order as svc_create_lab_order
from app.services.lab_service import get_lab_order as svc_get_lab_order
from app.services.lab_service import register_lab_result as svc_register_lab_result
from app.services.lab_service import update_lab_order_status as svc_update_lab_order_status

router = APIRouter(prefix="/api/v1/lab-orders", tags=["Lab"], dependencies=[Depends(require_module("operaciones"))])


@router.post("", response_model=LabOrderRead, status_code=status.HTTP_201_CREATED)
def create_lab_order(
    data: LabOrderCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    return svc_create_lab_order(db, current_user.tenant_id, data, current_user.id)


@router.get("", response_model=list[LabOrderRead])
def list_lab_orders(
    patient_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(LabOrder).filter(LabOrder.tenant_id == current_user.tenant_id)
    if patient_id:
        query = query.filter(LabOrder.patient_id == uuid_bytes(patient_id))
    return query.order_by(LabOrder.order_datetime.desc()).all()


@router.get("/{order_id}", response_model=LabOrderDetail)
def get_lab_order(order_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    order = svc_get_lab_order(db, order_id.bytes, current_user.tenant_id)
    data = model_to_dict(order)
    data["items"] = db.query(LabOrderItem).filter(LabOrderItem.lab_order_id == order.id, LabOrderItem.tenant_id == current_user.tenant_id).all()
    data["results"] = db.query(LabResult).filter(LabResult.lab_order_id == order.id, LabResult.tenant_id == current_user.tenant_id).all()
    data["specimens"] = []
    return data


@router.patch("/{order_id}/status", response_model=LabOrderRead)
def update_lab_order_status(
    order_id: UUID,
    data: LabOrderUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.nurse, UserRole.doctor)),
):
    return svc_update_lab_order_status(db, order_id.bytes, current_user.tenant_id, data, current_user.id)


@router.post("/{order_id}/results", response_model=LabResultRead, status_code=status.HTTP_201_CREATED)
def create_lab_result(
    order_id: UUID,
    data: LabResultCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.nurse, UserRole.doctor)),
):
    result, _alert = svc_register_lab_result(db, order_id.bytes, current_user.tenant_id, data, current_user.id)
    return result
