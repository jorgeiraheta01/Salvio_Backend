from datetime import date, datetime, time, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor_schedule import DoctorAbsence, DoctorWeeklyHours
from app.models.tenant import User
from app.schemas.doctor_schedule import DoctorAbsenceCreate, WeeklyHoursEntry
from app.services._utils import commit_or_409, new_uuid_bytes, not_found, uuid_bytes

# Estados de cita que realmente ocupan la agenda -- una cancelada/no-show no
# debe seguir bloqueando el horario para nuevas citas.
ACTIVE_APPOINTMENT_STATUSES = {
    AppointmentStatus.scheduled,
    AppointmentStatus.confirmed,
    AppointmentStatus.checked_in,
    AppointmentStatus.in_consultation,
    AppointmentStatus.completed,
}

# Duracion fija de cada consulta -- el schema no tiene columna de duracion,
# asi que se asume este bloque para el choque de horario (ver assert_doctor_available).
APPOINTMENT_DURATION = timedelta(minutes=30)


def _get_doctor_or_404(db: Session, tenant_id: str, doctor_id) -> User:
    doctor = db.query(User).filter(User.id == uuid_bytes(doctor_id), User.tenant_id == tenant_id, User.deleted_at.is_(None)).first()
    if not doctor:
        raise not_found("Doctor not found.")
    return doctor


def list_weekly_hours(db: Session, tenant_id: str, doctor_id) -> list[DoctorWeeklyHours]:
    _get_doctor_or_404(db, tenant_id, doctor_id)
    return (
        db.query(DoctorWeeklyHours)
        .filter(DoctorWeeklyHours.tenant_id == tenant_id, DoctorWeeklyHours.doctor_id == uuid_bytes(doctor_id))
        .order_by(DoctorWeeklyHours.day_of_week, DoctorWeeklyHours.start_time)
        .all()
    )


def set_weekly_hours(db: Session, tenant_id: str, doctor_id, entries: list[WeeklyHoursEntry]) -> list[DoctorWeeklyHours]:
    """Reemplaza TODO el horario semanal del medico de una vez -- se edita
    como plantilla completa (full-time/part-time), no fila por fila, para
    que no queden huecos o solapes a medio configurar."""
    _get_doctor_or_404(db, tenant_id, doctor_id)
    for entry in entries:
        if entry.end_time <= entry.start_time:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="end_time debe ser posterior a start_time.")

    db.query(DoctorWeeklyHours).filter(DoctorWeeklyHours.tenant_id == tenant_id, DoctorWeeklyHours.doctor_id == uuid_bytes(doctor_id)).delete()
    rows = [
        DoctorWeeklyHours(
            id=new_uuid_bytes(),
            tenant_id=tenant_id,
            doctor_id=uuid_bytes(doctor_id),
            day_of_week=entry.day_of_week,
            start_time=entry.start_time,
            end_time=entry.end_time,
        )
        for entry in entries
    ]
    db.add_all(rows)
    commit_or_409(db)
    return list_weekly_hours(db, tenant_id, doctor_id)


def list_absences(db: Session, tenant_id: str, doctor_id) -> list[DoctorAbsence]:
    _get_doctor_or_404(db, tenant_id, doctor_id)
    return (
        db.query(DoctorAbsence)
        .filter(DoctorAbsence.tenant_id == tenant_id, DoctorAbsence.doctor_id == uuid_bytes(doctor_id))
        .order_by(DoctorAbsence.start_date.desc())
        .all()
    )


def create_absence(db: Session, tenant_id: str, doctor_id, data: DoctorAbsenceCreate) -> DoctorAbsence:
    _get_doctor_or_404(db, tenant_id, doctor_id)
    if data.end_date < data.start_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="end_date debe ser posterior o igual a start_date.")
    absence = DoctorAbsence(
        id=new_uuid_bytes(),
        tenant_id=tenant_id,
        doctor_id=uuid_bytes(doctor_id),
        start_date=data.start_date,
        end_date=data.end_date,
        reason=data.reason,
    )
    db.add(absence)
    commit_or_409(db)
    db.refresh(absence)
    return absence


def delete_absence(db: Session, tenant_id: str, doctor_id, absence_id) -> None:
    absence = (
        db.query(DoctorAbsence)
        .filter(DoctorAbsence.id == uuid_bytes(absence_id), DoctorAbsence.tenant_id == tenant_id, DoctorAbsence.doctor_id == uuid_bytes(doctor_id))
        .first()
    )
    if not absence:
        raise not_found("Absence not found.")
    db.delete(absence)
    commit_or_409(db)


def assert_doctor_available(db: Session, tenant_id: str, doctor_id, scheduled_at: datetime, *, exclude_appointment_id: bytes | None = None) -> None:
    """Valida el espacio de agenda del medico antes de crear/reprogramar una
    cita: sin ausencia activa, dentro de su horario semanal (si configuro
    uno -- sin fila = sin restriccion, ver DoctorWeeklyHours) y sin choque
    con otra cita ya agendada que se solape su bloque de 30 minutos
    (APPOINTMENT_DURATION) con el de la nueva cita, y que la hora no sea
    retroactiva (el frontend ya lo valida, esto es la misma regla del lado
    del servidor por si alguien pega directo a la API)."""
    naive_scheduled_at = scheduled_at.astimezone(timezone.utc).replace(tzinfo=None) if scheduled_at.tzinfo is not None else scheduled_at
    if naive_scheduled_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No se pueden agendar citas en una fecha/hora pasada.")

    doctor_id_bytes = uuid_bytes(doctor_id)
    target_date = naive_scheduled_at.date()

    absence = (
        db.query(DoctorAbsence)
        .filter(
            DoctorAbsence.tenant_id == tenant_id,
            DoctorAbsence.doctor_id == doctor_id_bytes,
            DoctorAbsence.start_date <= target_date,
            DoctorAbsence.end_date >= target_date,
        )
        .first()
    )
    if absence is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El medico no esta disponible en esa fecha (ausencia registrada).")

    weekly_rows = db.query(DoctorWeeklyHours).filter(DoctorWeeklyHours.tenant_id == tenant_id, DoctorWeeklyHours.doctor_id == doctor_id_bytes).all()
    if weekly_rows:
        iso_day = naive_scheduled_at.weekday()  # 0=lunes .. 6=domingo, coincide con la convencion de day_of_week
        target_time = naive_scheduled_at.time()
        in_range = any(row.day_of_week == iso_day and row.start_time <= target_time < row.end_time for row in weekly_rows)
        if not in_range:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esa hora esta fuera del horario configurado del medico.")

    collision_query = db.query(Appointment).filter(
        Appointment.tenant_id == tenant_id,
        Appointment.doctor_id == doctor_id_bytes,
        Appointment.scheduled_at > naive_scheduled_at - APPOINTMENT_DURATION,
        Appointment.scheduled_at < naive_scheduled_at + APPOINTMENT_DURATION,
        Appointment.deleted_at.is_(None),
        Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
    )
    if exclude_appointment_id is not None:
        collision_query = collision_query.filter(Appointment.id != exclude_appointment_id)
    if collision_query.first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El medico ya tiene una cita agendada a esa hora.")
