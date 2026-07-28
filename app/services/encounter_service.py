from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.encounter import Encounter, EncounterStatus
from app.models.patient import Patient
from app.models.tenant import User
from app.routers._utils import uuid_bytes


def resolve_request_tenant(request: Request, current_user: User) -> str:
    tenant_id = getattr(request.state, "tenant", None) or getattr(request.state, "tenant_id", None)
    if not tenant_id:
        return current_user.tenant_id
    if tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant context does not match the authenticated user.")
    return tenant_id


def get_patient_or_404(db: Session, patient_id: bytes, tenant_id: str) -> Patient:
    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id, Patient.tenant_id == tenant_id, Patient.deleted_at.is_(None))
        .first()
    )
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")
    return patient


def get_encounter_or_404(db: Session, encounter_id: UUID | bytes, tenant_id: str) -> Encounter:
    encounter = db.query(Encounter).filter(Encounter.id == uuid_bytes(encounter_id), Encounter.tenant_id == tenant_id).first()
    if not encounter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encounter not found.")
    return encounter


def ensure_encounter_owner(encounter: Encounter, current_user: User) -> None:
    if encounter.doctor_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned doctor can modify this encounter.")


def ensure_encounter_editable(encounter: Encounter) -> None:
    if encounter.status == EncounterStatus.closed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Closed encounters are immutable.")


def ensure_version(expected_version: int, current_version: int, message: str = "The record was updated by another session.") -> None:
    if expected_version != current_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def get_appointment_for_encounter(db: Session, appointment_id: UUID, tenant_id: str, current_user: User) -> Appointment:
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id.bytes, Appointment.tenant_id == tenant_id, Appointment.deleted_at.is_(None))
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    if appointment.doctor_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The appointment does not belong to the authenticated doctor.")
    return appointment


def sync_appointment_status(appointment: Appointment, new_status: AppointmentStatus) -> None:
    current_status = appointment.status
    current_value = current_status.value if hasattr(current_status, "value") else str(current_status)
    target_value = new_status.value if hasattr(new_status, "value") else str(new_status)
    if current_value != target_value:
        appointment.status = new_status
        appointment.updated_at = datetime.now(timezone.utc)
