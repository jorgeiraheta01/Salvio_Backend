from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.db import get_db
from app.dependencies.module_gate import require_module
from app.models.tenant import User, UserRole
from app.routers._utils import audit_mutation, model_to_dict
from app.schemas.common import MessageResponse
from app.schemas.doctor_schedule import DoctorAbsenceCreate, DoctorAbsenceRead, WeeklyHoursRead, WeeklyHoursSetRequest
from app.services.doctor_schedule_service import create_absence as svc_create_absence
from app.services.doctor_schedule_service import delete_absence as svc_delete_absence
from app.services.doctor_schedule_service import list_absences as svc_list_absences
from app.services.doctor_schedule_service import list_weekly_hours as svc_list_weekly_hours
from app.services.doctor_schedule_service import set_weekly_hours as svc_set_weekly_hours

router = APIRouter(prefix="/api/v1/doctors", tags=["Doctor Schedule"], dependencies=[Depends(require_module("agenda"))])

# Solo quien administra la clinica (o el propio flujo de agenda via recepcion)
# puede tocar el horario de un medico -- un medico cambiando su propio
# horario sin pasar por admin/recepcion queda fuera de alcance por ahora.
SCHEDULE_MANAGE_ROLES = (UserRole.clinic_admin, UserRole.receptionist)


@router.get("/{doctor_id}/weekly-hours", response_model=list[WeeklyHoursRead])
def get_weekly_hours(doctor_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = svc_list_weekly_hours(db, current_user.tenant_id, doctor_id)
    return [WeeklyHoursRead(**model_to_dict(r)) for r in rows]


@router.put("/{doctor_id}/weekly-hours", response_model=list[WeeklyHoursRead])
def put_weekly_hours(
    doctor_id: UUID,
    payload: WeeklyHoursSetRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*SCHEDULE_MANAGE_ROLES)),
):
    rows = svc_set_weekly_hours(db, current_user.tenant_id, doctor_id, payload.entries)
    audit_mutation(
        db,
        request,
        current_user,
        action="set_weekly_hours",
        table_name="doctor_weekly_hours",
        record_id=doctor_id.bytes,
        new_values={"entries": [e.model_dump(mode="json") for e in payload.entries]},
    )
    return [WeeklyHoursRead(**model_to_dict(r)) for r in rows]


@router.get("/{doctor_id}/absences", response_model=list[DoctorAbsenceRead])
def get_absences(doctor_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = svc_list_absences(db, current_user.tenant_id, doctor_id)
    return [DoctorAbsenceRead(**model_to_dict(r)) for r in rows]


@router.post("/{doctor_id}/absences", response_model=DoctorAbsenceRead, status_code=201)
def post_absence(
    doctor_id: UUID,
    payload: DoctorAbsenceCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*SCHEDULE_MANAGE_ROLES)),
):
    row = svc_create_absence(db, current_user.tenant_id, doctor_id, payload)
    audit_mutation(db, request, current_user, action="create_absence", table_name="doctor_absences", record_id=row.id, new_values=model_to_dict(row))
    return DoctorAbsenceRead(**model_to_dict(row))


@router.delete("/{doctor_id}/absences/{absence_id}", response_model=MessageResponse)
def delete_absence(
    doctor_id: UUID,
    absence_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*SCHEDULE_MANAGE_ROLES)),
):
    svc_delete_absence(db, current_user.tenant_id, doctor_id, absence_id)
    audit_mutation(db, request, current_user, action="delete_absence", table_name="doctor_absences", record_id=absence_id.bytes, new_values=None)
    return MessageResponse(message="OK")
