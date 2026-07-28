from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.patient import Patient, PatientAllergy
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services._utils import audit, commit_or_409, data_for_model, model_to_dict, new_uuid_bytes, not_found, uuid_bytes


def generate_mrn(db: Session, tenant_id: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"MRN-{today}-"
    count = (
        db.query(func.count(Patient.id))
        .filter(Patient.tenant_id == tenant_id, Patient.medical_record_number.like(f"{prefix}%"))
        .scalar()
        or 0
    )
    return f"{prefix}{count + 1:04d}"


def create_patient(db: Session, tenant_id: str, data: PatientCreate, user_id: bytes) -> Patient:
    if data.dui:
        duplicate = db.query(Patient).filter(Patient.tenant_id == tenant_id, Patient.dui == data.dui).first()
        if duplicate:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A patient with this DUI already exists in this tenant.")
    payload = data_for_model(data, Patient, tenant_id=tenant_id)
    payload["id"] = new_uuid_bytes()
    payload["medical_record_number"] = generate_mrn(db, tenant_id)
    patient = Patient(**payload)
    db.add(patient)
    db.flush()
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="patients", record_id=patient.id, new_values=model_to_dict(patient))
    commit_or_409(db, "A patient with this DUI or MRN already exists.")
    db.refresh(patient)
    return patient


def get_patient(db: Session, patient_id: bytes, tenant_id: str) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.tenant_id == tenant_id, Patient.deleted_at.is_(None)).first()
    if not patient:
        raise not_found("Patient not found.")
    return patient


def update_patient(db: Session, patient_id: bytes, tenant_id: str, data: PatientUpdate, user_id: bytes) -> Patient:
    payload = data.model_dump(exclude_unset=True)
    if "tenant_id" in payload or "medical_record_number" in payload:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="tenant_id and medical_record_number cannot be changed.")
    patient = get_patient(db, patient_id, tenant_id)
    old = model_to_dict(patient)
    if "dui" in payload and payload["dui"]:
        duplicate = db.query(Patient).filter(Patient.tenant_id == tenant_id, Patient.dui == payload["dui"], Patient.id != patient_id).first()
        if duplicate:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A patient with this DUI already exists in this tenant.")
    update_payload = data_for_model(data, Patient)
    update_payload.pop("id", None)  # data_for_model auto-generates an id for create paths; never apply it on update
    for key, value in update_payload.items():
        setattr(patient, key, value)
    audit(db, user_id=user_id, tenant_id=tenant_id, action="UPDATE", table_name="patients", record_id=patient.id, old_values=old, new_values=model_to_dict(patient))
    commit_or_409(db)
    db.refresh(patient)
    return patient


def soft_delete_patient(db: Session, patient_id: bytes, tenant_id: str, user_id: bytes) -> None:
    patient = get_patient(db, patient_id, tenant_id)
    old = model_to_dict(patient)
    patient.deleted_at = datetime.now(timezone.utc)
    audit(db, user_id=user_id, tenant_id=tenant_id, action="DELETE", table_name="patients", record_id=patient.id, old_values=old, new_values=model_to_dict(patient))
    commit_or_409(db)


def search_patients(db: Session, tenant_id: str, q: str | None, page: int, limit: int) -> tuple[list[Patient], int]:
    query = db.query(Patient).filter(Patient.tenant_id == tenant_id, Patient.deleted_at.is_(None))
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                Patient.first_name.ilike(pattern),
                Patient.last_name.ilike(pattern),
                Patient.dui.ilike(pattern),
                Patient.medical_record_number.ilike(pattern),
            )
        )
    total = query.count()
    patients = query.order_by(Patient.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return patients, total


def check_allergy_alert(db: Session, patient_id: bytes, medication_names: list[str]) -> list[dict]:
    allergies = db.query(PatientAllergy).filter(PatientAllergy.patient_id == patient_id, PatientAllergy.is_active.is_(True)).all()
    alerts: list[dict] = []
    for medication_name in medication_names:
        medication_lower = medication_name.lower()
        for allergy in allergies:
            allergen = (allergy.allergen or "").lower()
            if allergen and allergen in medication_lower:
                alerts.append(
                    {
                        "medication": medication_name,
                        "allergen": allergy.allergen,
                        "severity": allergy.severity.value if hasattr(allergy.severity, "value") else str(allergy.severity),
                        "reaction": allergy.reaction,
                    }
                )
    return alerts
