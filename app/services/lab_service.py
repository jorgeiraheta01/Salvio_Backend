from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.lab import LabOrder, LabOrderItem, LabOrderStatus, LabResult
from app.models.patient import Patient
from app.schemas.common import ClinicalAlert
from app.schemas.lab import LabOrderCreate, LabOrderUpdate, LabResultCreate
from app.services._utils import audit, commit_or_409, data_for_model, model_to_dict, new_uuid_bytes, not_found

# H-04: orden de laboratorio nunca retrocede -- de cualquier estado no
# terminal se puede cancelar, pero no "reabrir" uno ya completado/cancelado.
LAB_ALLOWED_TRANSITIONS = {
    LabOrderStatus.ordered: {LabOrderStatus.collected, LabOrderStatus.cancelled},
    LabOrderStatus.collected: {LabOrderStatus.processing, LabOrderStatus.cancelled},
    LabOrderStatus.processing: {LabOrderStatus.completed, LabOrderStatus.cancelled},
    LabOrderStatus.completed: set(),
    LabOrderStatus.cancelled: set(),
}


def _alert_append(alert: ClinicalAlert, alert_type: str, message: str) -> None:
    alert.alert_triggered = True
    alert.alert_type.append(alert_type)
    alert.alert_messages.append(message)


def create_lab_order(db: Session, tenant_id: str, data: LabOrderCreate, user_id: bytes) -> LabOrder:
    patient = db.query(Patient).filter(Patient.id == data.patient_id.bytes, Patient.tenant_id == tenant_id, Patient.deleted_at.is_(None)).first()
    if not patient:
        raise not_found("Patient not found.")
    order = LabOrder(**data_for_model(data, LabOrder, exclude={"items"}, tenant_id=tenant_id))
    order.id = new_uuid_bytes()
    db.add(order)
    db.flush()
    for item in data.items:
        payload = data_for_model(item, LabOrderItem, tenant_id=tenant_id)
        payload["id"] = new_uuid_bytes()
        payload["lab_order_id"] = order.id
        db.add(LabOrderItem(**payload))
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="lab_orders", record_id=order.id, new_values=model_to_dict(order))
    commit_or_409(db)
    db.refresh(order)
    return order


def get_lab_order(db: Session, order_id: bytes, tenant_id: str) -> LabOrder:
    order = db.query(LabOrder).filter(LabOrder.id == order_id, LabOrder.tenant_id == tenant_id).first()
    if not order:
        raise not_found("Lab order not found.")
    return order


def update_lab_order_status(db: Session, order_id: bytes, tenant_id: str, data: LabOrderUpdate, user_id: bytes) -> LabOrder:
    order = get_lab_order(db, order_id, tenant_id)
    if data.status is not None and data.status != order.status:
        if data.status not in LAB_ALLOWED_TRANSITIONS[order.status]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No se puede pasar la orden de laboratorio de '{order.status.value}' a '{data.status.value}'",
            )
    old = model_to_dict(order)
    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(order, field, value)
    audit(db, user_id=user_id, tenant_id=tenant_id, action="UPDATE", table_name="lab_orders", record_id=order.id, old_values=old, new_values=model_to_dict(order))
    commit_or_409(db)
    db.refresh(order)
    return order


def register_lab_result(db: Session, order_id: bytes, tenant_id: str, data: LabResultCreate, user_id: bytes) -> tuple[LabResult, ClinicalAlert]:
    get_lab_order(db, order_id, tenant_id)
    alert = ClinicalAlert()
    if data.is_abnormal:
        _alert_append(alert, "lab_abnormal", "Lab result marked as abnormal")
    if data.numeric_value is not None and data.critical_low is not None and data.numeric_value < data.critical_low:
        _alert_append(alert, "lab_critical_low", "Lab result is below critical low threshold")
    if data.numeric_value is not None and data.critical_high is not None and data.numeric_value > data.critical_high:
        _alert_append(alert, "lab_critical_high", "Lab result is above critical high threshold")
    result = LabResult(**data_for_model(data, LabResult, exclude={"alert", "critical_low", "critical_high"}, tenant_id=tenant_id))
    result.id = new_uuid_bytes()
    result.lab_order_id = order_id
    db.add(result)
    db.flush()
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="lab_results", record_id=result.id, new_values=model_to_dict(result))
    commit_or_409(db)
    db.refresh(result)
    return result, alert
