from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, PatientAdmission, TriageRecord
from app.models.patient import Patient
from app.models.tenant import User
from app.schemas.appointment import AppointmentCreate, PatientAdmissionCreate, TriageRecordCreate
from app.services._utils import audit, commit_or_409, data_for_model, model_to_dict, new_uuid_bytes, not_found
from app.services.doctor_schedule_service import assert_doctor_available

ALLOWED_TRANSITIONS = {
    "scheduled": {"confirmed", "cancelled", "no_show", "rescheduled"},
    "confirmed": {"checked_in", "cancelled", "no_show", "rescheduled"},
    "checked_in": {"in_consultation", "cancelled"},
    "in_consultation": {"completed"},
    "completed": set(),
    "cancelled": set(),
    "no_show": set(),
    "rescheduled": set(),
}


def _value(status_value) -> str:
    return status_value.value if hasattr(status_value, "value") else str(status_value)


def validate_status_transition(current: str, new: str) -> None:
    if new not in ALLOWED_TRANSITIONS[current]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Cannot transition appointment from '{current}' to '{new}'")


def create_appointment(db: Session, tenant_id: str, data: AppointmentCreate, user_id: bytes) -> Appointment:
    patient = db.query(Patient).filter(Patient.id == data.patient_id.bytes, Patient.tenant_id == tenant_id, Patient.deleted_at.is_(None)).first()
    doctor = db.query(User).filter(User.id == data.doctor_id.bytes, User.tenant_id == tenant_id, User.deleted_at.is_(None)).first()
    if not patient or not doctor:
        raise not_found("Patient or doctor not found.")
    assert_doctor_available(db, tenant_id, data.doctor_id, data.scheduled_at)
    payload = data_for_model(data, Appointment, tenant_id=tenant_id)
    payload["id"] = new_uuid_bytes()
    payload["status"] = "scheduled"
    appointment = Appointment(**payload)
    db.add(appointment)
    db.flush()
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="appointments", record_id=appointment.id, new_values=model_to_dict(appointment))
    commit_or_409(db)
    db.refresh(appointment)
    return appointment


def update_appointment_status(db: Session, appt_id: bytes, tenant_id: str, new_status: str, reason: str | None, user_id: bytes) -> Appointment:
    appointment = db.query(Appointment).filter(Appointment.id == appt_id, Appointment.tenant_id == tenant_id, Appointment.deleted_at.is_(None)).first()
    if not appointment:
        raise not_found("Appointment not found.")
    current = _value(appointment.status)
    validate_status_transition(current, new_status)
    if new_status in {"cancelled", "no_show", "rescheduled"} and not reason:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="reason is required for this status")
    old = model_to_dict(appointment)
    appointment.status = new_status
    audit(db, user_id=user_id, tenant_id=tenant_id, action="UPDATE", table_name="appointments", record_id=appointment.id, old_values=old, new_values=model_to_dict(appointment))
    commit_or_409(db)
    db.refresh(appointment)
    return appointment


def reschedule_appointment(
    db: Session,
    appt_id: bytes,
    tenant_id: str,
    new_scheduled_at,
    new_doctor_id,
    reason: str,
    user_id: bytes,
) -> Appointment:
    """Reprogramar de verdad: crea la cita nueva (fecha/medico elegibles,
    validada contra horario/ausencia/choque del medico) Y marca la vieja
    como 'rescheduled' con el motivo, en la misma transaccion -- antes solo
    se marcaba la vieja sin crear nunca la nueva."""
    old_appointment = db.query(Appointment).filter(Appointment.id == appt_id, Appointment.tenant_id == tenant_id, Appointment.deleted_at.is_(None)).first()
    if not old_appointment:
        raise not_found("Appointment not found.")
    current = _value(old_appointment.status)
    validate_status_transition(current, "rescheduled")

    doctor_id = new_doctor_id.bytes if new_doctor_id is not None else old_appointment.doctor_id
    doctor = db.query(User).filter(User.id == doctor_id, User.tenant_id == tenant_id, User.deleted_at.is_(None)).first()
    if not doctor:
        raise not_found("Doctor not found.")

    assert_doctor_available(db, tenant_id, doctor_id, new_scheduled_at)

    new_appointment = Appointment(
        id=new_uuid_bytes(),
        tenant_id=tenant_id,
        patient_id=old_appointment.patient_id,
        doctor_id=doctor_id,
        scheduled_at=new_scheduled_at,
        appointment_type=old_appointment.appointment_type,
        status="scheduled",
        notes=old_appointment.notes,
    )
    db.add(new_appointment)

    old_values = model_to_dict(old_appointment)
    old_appointment.status = "rescheduled"

    db.flush()
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="appointments", record_id=new_appointment.id, new_values=model_to_dict(new_appointment))
    audit(
        db,
        user_id=user_id,
        tenant_id=tenant_id,
        action="UPDATE",
        table_name="appointments",
        record_id=old_appointment.id,
        old_values=old_values,
        new_values={**model_to_dict(old_appointment), "reschedule_reason": reason, "rescheduled_to": model_to_dict(new_appointment)["id"]},
    )
    commit_or_409(db)
    db.refresh(new_appointment)
    return new_appointment


def create_admission(db: Session, tenant_id: str, data: PatientAdmissionCreate, user_id: bytes) -> PatientAdmission:
    admission = PatientAdmission(**data_for_model(data, PatientAdmission, tenant_id=tenant_id))
    admission.id = new_uuid_bytes()
    db.add(admission)
    db.flush()
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="patient_admissions", record_id=admission.id, new_values=model_to_dict(admission))
    commit_or_409(db)
    db.refresh(admission)
    return admission


def create_triage(db: Session, tenant_id: str, data: TriageRecordCreate, user_id: bytes) -> TriageRecord:
    triage = TriageRecord(**data_for_model(data, TriageRecord, exclude={"alert"}, tenant_id=tenant_id))
    triage.id = new_uuid_bytes()
    db.add(triage)
    db.flush()
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="triage_records", record_id=triage.id, new_values=model_to_dict(triage))
    commit_or_409(db)
    db.refresh(triage)
    return triage
