from datetime import date as date_type, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.db import get_db
from app.dependencies.module_gate import require_module
from app.models.appointment import Appointment, AppointmentStatus, PatientAdmission, TriageRecord
from app.models.patient import Patient
from app.models.tenant import User, UserRole
from app.routers._utils import audit_mutation, commit_or_409, data_for_create, data_for_model, ensure_patient_exists, get_by_id_or_404, local_day_utc_range, model_to_dict, uuid_bytes
from app.schemas.appointment import (
    APPOINTMENT_STATUS_ORDER,
    AppointmentCreate,
    AppointmentRead,
    AppointmentRescheduleRequest,
    AppointmentStatusUpdate,
    PatientAdmissionCreate,
    PatientAdmissionRead,
    TriageRecordCreate,
    TriageRecordRead,
)
from app.services.appointment_service import create_admission as svc_create_admission
from app.services.appointment_service import create_appointment as svc_create_appointment
from app.services.appointment_service import create_triage as svc_create_triage
from app.services.appointment_service import reschedule_appointment as svc_reschedule_appointment
from app.services.appointment_service import update_appointment_status as svc_update_appointment_status

router = APIRouter(prefix="/api/v1/appointments", tags=["Appointments"], dependencies=[Depends(require_module("agenda"))])
APPOINTMENT_ROLES = (UserRole.clinic_admin, UserRole.doctor, UserRole.resident, UserRole.receptionist)


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
def create_appointment(
    data: AppointmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*APPOINTMENT_ROLES)),
):
    return svc_create_appointment(db, current_user.tenant_id, data, current_user.id)


@router.get("", response_model=list[AppointmentRead])
def list_appointments(
    doctor_id: UUID | None = Query(default=None),
    patient_id: UUID | None = Query(default=None),
    date: date_type | None = Query(default=None),
    status_filter: AppointmentStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Appointment).filter(Appointment.tenant_id == current_user.tenant_id, Appointment.deleted_at.is_(None))
    if doctor_id:
        query = query.filter(Appointment.doctor_id == uuid_bytes(doctor_id))
    if patient_id:
        query = query.filter(Appointment.patient_id == uuid_bytes(patient_id))
    if status_filter:
        query = query.filter(Appointment.status == status_filter)
    if date:
        start_utc, end_utc = local_day_utc_range(date)
        query = query.filter(Appointment.scheduled_at >= start_utc, Appointment.scheduled_at < end_utc)
    return query.order_by(Appointment.scheduled_at.asc()).all()


@router.patch("/{appointment_id}/status", response_model=AppointmentRead)
def update_appointment_status(
    appointment_id: UUID,
    data: AppointmentStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*APPOINTMENT_ROLES)),
):
    return svc_update_appointment_status(db, appointment_id.bytes, current_user.tenant_id, data.status.value, data.reason, current_user.id)


@router.post("/{appointment_id}/reschedule", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
def reschedule_appointment(
    appointment_id: UUID,
    data: AppointmentRescheduleRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*APPOINTMENT_ROLES)),
):
    return svc_reschedule_appointment(
        db,
        appointment_id.bytes,
        current_user.tenant_id,
        data.new_scheduled_at,
        data.new_doctor_id,
        data.reason,
        current_user.id,
    )


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appointment(
    appointment_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*APPOINTMENT_ROLES)),
):
    appointment = get_by_id_or_404(db, Appointment, appointment_id, current_user.tenant_id)
    old = model_to_dict(appointment)
    appointment.deleted_at = datetime.now(timezone.utc)
    audit_mutation(db, request, current_user, action="soft_delete", table_name="appointments", record_id=appointment.id, old_values=old, new_values=model_to_dict(appointment))
    commit_or_409(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{appointment_id}/admissions", response_model=PatientAdmissionRead, status_code=status.HTTP_201_CREATED)
def create_admission(
    appointment_id: UUID,
    data: PatientAdmissionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*APPOINTMENT_ROLES)),
):
    get_by_id_or_404(db, Appointment, appointment_id, current_user.tenant_id)
    return svc_create_admission(db, current_user.tenant_id, data, current_user.id)


@router.post("/{appointment_id}/triage", response_model=TriageRecordRead, status_code=status.HTTP_201_CREATED)
def create_triage(
    appointment_id: UUID,
    data: TriageRecordCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.nurse, UserRole.doctor, UserRole.resident)),
):
    get_by_id_or_404(db, Appointment, appointment_id, current_user.tenant_id)
    data = data.model_copy(update={"appointment_id": appointment_id})
    return svc_create_triage(db, current_user.tenant_id, data, current_user.id)
