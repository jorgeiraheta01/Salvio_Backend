from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.db import get_db
from app.models.appointment import AppointmentStatus
from app.models.clinical import ClinicalNote, RecordDiagnosis, VitalSign
from app.models.encounter import ClinicalOrder, Encounter, EncounterStatus
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.tenant import User, UserRole
from app.routers._utils import audit_mutation, commit_or_409, model_to_dict
from app.schemas.encounter import EncounterCloseRequest, EncounterDoctorSummary, EncounterPatientSummary, EncounterRead, EncounterSectionSummary, EncounterStartRequest
from app.schemas.common import MessageResponse, patient_age_years
from app.services._utils import new_uuid_bytes
from app.services.encounter_service import ensure_encounter_owner, ensure_version, get_appointment_for_encounter, get_encounter_or_404, get_patient_or_404, resolve_request_tenant, sync_appointment_status

router = APIRouter(prefix="/api/v1/encounters", tags=["Encounters"])


def _patient_summary(patient: Patient) -> EncounterPatientSummary:
    full_name = " ".join(part for part in [patient.first_name, patient.last_name] if part)
    age = patient_age_years(patient.date_of_birth) if getattr(patient, "date_of_birth", None) else None
    document = getattr(patient, "dui", None) or getattr(patient, "medical_record_number", None)
    return EncounterPatientSummary(id=UUID(bytes=patient.id), full_name=full_name, age=age, document=document)


def _doctor_summary(doctor: User) -> EncounterDoctorSummary:
    return EncounterDoctorSummary(id=UUID(bytes=doctor.id), full_name=doctor.full_name)


def _encounter_read(db: Session, encounter: Encounter, patient: Patient, doctor: User) -> EncounterRead:
    summary = EncounterSectionSummary(
        note_count=db.query(func.count(ClinicalNote.id)).filter(ClinicalNote.encounter_id == encounter.id, ClinicalNote.tenant_id == encounter.tenant_id).scalar() or 0,
        closed_note_count=db.query(func.count(ClinicalNote.id)).filter(ClinicalNote.encounter_id == encounter.id, ClinicalNote.tenant_id == encounter.tenant_id, ClinicalNote.is_closed.is_(True)).scalar() or 0,
        diagnosis_count=db.query(func.count(RecordDiagnosis.id)).filter(RecordDiagnosis.encounter_id == encounter.id, RecordDiagnosis.tenant_id == encounter.tenant_id).scalar() or 0,
        prescription_count=db.query(func.count(Prescription.id)).filter(Prescription.encounter_id == encounter.id, Prescription.tenant_id == encounter.tenant_id).scalar() or 0,
        vital_sign_count=db.query(func.count(VitalSign.id)).filter(VitalSign.encounter_id == encounter.id, VitalSign.tenant_id == encounter.tenant_id).scalar() or 0,
        order_count=db.query(func.count(ClinicalOrder.id)).filter(ClinicalOrder.encounter_id == encounter.id, ClinicalOrder.tenant_id == encounter.tenant_id).scalar() or 0,
    )
    return EncounterRead(
        id=UUID(bytes=encounter.id),
        appointment_id=UUID(bytes=encounter.appointment_id) if encounter.appointment_id else None,
        patient_id=UUID(bytes=encounter.patient_id),
        tenant_id=encounter.tenant_id,
        doctor_id=UUID(bytes=encounter.doctor_id),
        status=encounter.status,
        chief_complaint=encounter.chief_complaint,
        started_at=encounter.started_at,
        completed_at=encounter.completed_at,
        closed_at=encounter.closed_at,
        version=encounter.version,
        created_at=encounter.created_at,
        updated_at=encounter.updated_at,
        patient=_patient_summary(patient),
        doctor=_doctor_summary(doctor),
        summary=summary,
    )


@router.post("/start", response_model=EncounterRead, status_code=status.HTTP_201_CREATED)
def start_encounter(
    data: EncounterStartRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    tenant_id = resolve_request_tenant(request, current_user)
    appointment = None
    patient = None
    if data.appointment_id:
        appointment = get_appointment_for_encounter(db, data.appointment_id, tenant_id, current_user)
        patient = get_patient_or_404(db, appointment.patient_id, tenant_id)
        if data.patient_id and data.patient_id.bytes != appointment.patient_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="patient_id no coincide con el paciente de la cita.")
    else:
        if data.patient_id is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Se requiere patient_id cuando no se envia appointment_id.")
        patient = get_patient_or_404(db, data.patient_id.bytes, tenant_id)

    existing_query = db.query(Encounter).filter(
        Encounter.tenant_id == tenant_id,
        Encounter.doctor_id == current_user.id,
        Encounter.status.in_([EncounterStatus.active, EncounterStatus.completed]),
    )
    if appointment is not None:
        existing_query = existing_query.filter(Encounter.appointment_id == appointment.id)
    else:
        existing_query = existing_query.filter(Encounter.patient_id == patient.id)
    existing = existing_query.first()
    if existing:
        # La busqueda ya esta acotada a current_user.id, asi que este "conflicto"
        # nunca es un choque real con otro medico -- es siempre el mismo medico
        # reabriendo su propio encuentro activo (ej. salio de la pantalla y volvio
        # a darle a "Iniciar/reanudar consulta"). Devolver el existente en vez de
        # 409 hace que el flujo sea idempotente.
        return _encounter_read(db, existing, patient, current_user)
    encounter = Encounter(
        id=new_uuid_bytes(),
        appointment_id=appointment.id if appointment else None,
        patient_id=patient.id,
        tenant_id=tenant_id,
        doctor_id=current_user.id,
        status=EncounterStatus.active,
        chief_complaint=data.chief_complaint,
        created_by=current_user.id,
        updated_by=current_user.id,
        version=1,
    )
    db.add(encounter)
    if appointment is not None:
        sync_appointment_status(appointment, AppointmentStatus.in_consultation)
    audit_mutation(db, request, current_user, action="create", table_name="encounters", record_id=encounter.id, new_values=model_to_dict(encounter))
    commit_or_409(db)
    db.refresh(encounter)
    return _encounter_read(db, encounter, patient, current_user)


@router.get("", response_model=list[EncounterRead])
def list_encounters(
    patient_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    encounters = (
        db.query(Encounter)
        .filter(Encounter.tenant_id == current_user.tenant_id, Encounter.patient_id == patient_id.bytes)
        .order_by(Encounter.started_at.desc())
        .all()
    )
    results = []
    for encounter in encounters:
        patient = db.query(Patient).filter(Patient.id == encounter.patient_id, Patient.tenant_id == current_user.tenant_id).first()
        doctor = db.query(User).filter(User.id == encounter.doctor_id, User.tenant_id == current_user.tenant_id).first()
        if not patient or not doctor:
            continue
        results.append(_encounter_read(db, encounter, patient, doctor))
    return results


@router.get("/{encounter_id}", response_model=EncounterRead)
def get_encounter(
    encounter_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    encounter = get_encounter_or_404(db, encounter_id, current_user.tenant_id)
    patient = db.query(Patient).filter(Patient.id == encounter.patient_id, Patient.tenant_id == current_user.tenant_id).first()
    doctor = db.query(User).filter(User.id == encounter.doctor_id, User.tenant_id == current_user.tenant_id).first()
    if not patient or not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El encuentro hace referencia a datos no disponibles.")
    return _encounter_read(db, encounter, patient, doctor)


@router.post("/{encounter_id}/close", response_model=EncounterRead)
def close_encounter(
    encounter_id: UUID,
    data: EncounterCloseRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    tenant_id = resolve_request_tenant(request, current_user)
    encounter = get_encounter_or_404(db, encounter_id, tenant_id)
    ensure_encounter_owner(encounter, current_user)
    ensure_version(data.version, encounter.version)
    diagnosis_count = db.query(func.count(RecordDiagnosis.id)).filter(RecordDiagnosis.encounter_id == encounter.id, RecordDiagnosis.tenant_id == tenant_id).scalar() or 0
    closed_note_count = db.query(func.count(ClinicalNote.id)).filter(ClinicalNote.encounter_id == encounter.id, ClinicalNote.tenant_id == tenant_id, ClinicalNote.is_closed.is_(True)).scalar() or 0
    if diagnosis_count < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No se puede cerrar el encuentro sin al menos un diagnostico.")
    if closed_note_count < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No se puede cerrar el encuentro sin una nota clinica cerrada.")
    old = model_to_dict(encounter)
    encounter.status = EncounterStatus.closed
    encounter.closed_at = datetime.now(timezone.utc)
    if encounter.completed_at is None:
        encounter.completed_at = encounter.closed_at
    encounter.updated_by = current_user.id
    encounter.version += 1
    if encounter.appointment_id:
        appointment = get_appointment_for_encounter(db, UUID(bytes=encounter.appointment_id), tenant_id, current_user)
        sync_appointment_status(appointment, AppointmentStatus.completed)
    audit_mutation(db, request, current_user, action="close", table_name="encounters", record_id=encounter.id, old_values=old, new_values=model_to_dict(encounter))
    commit_or_409(db)
    db.refresh(encounter)
    patient = db.query(Patient).filter(Patient.id == encounter.patient_id, Patient.tenant_id == tenant_id).first()
    return _encounter_read(db, encounter, patient, current_user)
