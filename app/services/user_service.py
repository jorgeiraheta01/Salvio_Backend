from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.encounter import Encounter, EncounterStatus
from app.models.tenant import User
from app.schemas.user import UserUpdate
from app.services._utils import audit, commit_or_409, model_to_dict, not_found

# H-01/H-02: chequeo pragmatico, no exhaustivo. Solo se bloquea si el medico
# tiene citas futuras/abiertas o un encuentro activo -- el trabajo clinico
# realmente "en curso". Otras FK RESTRICT hacia users (ClinicalRecord.doctor_id,
# LabOrder.ordered_by, Interconsult.requesting_doctor, ClinicalOrder.ordered_by)
# deliberadamente no se verifican aqui: son registros historicos, no
# compromisos abiertos, y bloquearlos ademas haria la desactivacion
# impracticable para cualquier medico con historial. Limitacion documentada,
# no un descuido.
APPOINTMENT_OPEN_STATUSES = {
    AppointmentStatus.scheduled,
    AppointmentStatus.confirmed,
    AppointmentStatus.checked_in,
    AppointmentStatus.in_consultation,
}


def _get_active_user(db: Session, user_id: bytes, tenant_id: str) -> User:
    user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id, User.deleted_at.is_(None)).first()
    if not user:
        raise not_found("User not found.")
    return user


def update_user(db: Session, user_id: bytes, tenant_id: str, data: UserUpdate, actor_id: bytes) -> User:
    user = _get_active_user(db, user_id, tenant_id)
    old = model_to_dict(user)
    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(user, field, value)
    audit(db, user_id=actor_id, tenant_id=tenant_id, action="UPDATE", table_name="users", record_id=user.id, old_values=old, new_values=model_to_dict(user))
    commit_or_409(db)
    db.refresh(user)
    return user


def deactivate_user(db: Session, user_id: bytes, tenant_id: str, actor_id: bytes) -> User:
    user = _get_active_user(db, user_id, tenant_id)

    open_appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == user_id,
            Appointment.tenant_id == tenant_id,
            Appointment.deleted_at.is_(None),
            Appointment.status.in_(APPOINTMENT_OPEN_STATUSES),
            Appointment.scheduled_at >= datetime.now(timezone.utc),
        )
        .count()
    )
    if open_appointments:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede desactivar: el medico tiene {open_appointments} cita(s) futura(s)/abierta(s).",
        )

    active_encounters = (
        db.query(Encounter)
        .filter(Encounter.doctor_id == user_id, Encounter.tenant_id == tenant_id, Encounter.status == EncounterStatus.active)
        .count()
    )
    if active_encounters:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede desactivar: el medico tiene {active_encounters} encuentro(s) activo(s).",
        )

    old = model_to_dict(user)
    user.is_active = False
    audit(db, user_id=actor_id, tenant_id=tenant_id, action="UPDATE", table_name="users", record_id=user.id, old_values=old, new_values=model_to_dict(user))
    commit_or_409(db)
    db.refresh(user)
    return user


def reactivate_user(db: Session, user_id: bytes, tenant_id: str, actor_id: bytes) -> User:
    user = _get_active_user(db, user_id, tenant_id)
    old = model_to_dict(user)
    user.is_active = True
    audit(db, user_id=actor_id, tenant_id=tenant_id, action="UPDATE", table_name="users", record_id=user.id, old_values=old, new_values=model_to_dict(user))
    commit_or_409(db)
    db.refresh(user)
    return user
