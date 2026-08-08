from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.clinical import ClinicalNote, ClinicalRecord, ClinicalRecordStatus, NoteType, RecordDiagnosis
from app.models.tenant import User, UserRole
from app.schemas.clinical import ClinicalRecordCreate, ClinicalRecordUpdate
from app.services._utils import audit, commit_or_409, data_for_model, model_to_dict, new_uuid_bytes, not_found


def create_clinical_record(db: Session, tenant_id: str, data: ClinicalRecordCreate, doctor: User) -> ClinicalRecord:
    if doctor.role not in {UserRole.doctor, UserRole.resident}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo los medicos y residentes pueden crear expedientes clinicos.")
    payload = data_for_model(data, ClinicalRecord, tenant_id=tenant_id)
    payload["id"] = new_uuid_bytes()
    payload["status"] = ClinicalRecordStatus.draft
    payload["doctor_id"] = doctor.id
    payload["doctor_name"] = doctor.full_name
    record = ClinicalRecord(**payload)
    db.add(record)
    db.flush()
    audit(db, user_id=doctor.id, tenant_id=tenant_id, action="INSERT", table_name="clinical_records", record_id=record.id, new_values=model_to_dict(record))
    commit_or_409(db)
    db.refresh(record)
    return record


def get_clinical_record(db: Session, record_id: bytes, tenant_id: str) -> ClinicalRecord:
    record = db.query(ClinicalRecord).filter(ClinicalRecord.id == record_id, ClinicalRecord.tenant_id == tenant_id, ClinicalRecord.deleted_at.is_(None)).first()
    if not record:
        raise not_found("Clinical record not found.")
    return record


def update_clinical_record(db: Session, record_id: bytes, tenant_id: str, data: ClinicalRecordUpdate, user_id: bytes) -> ClinicalRecord:
    record = get_clinical_record(db, record_id, tenant_id)
    if record.status == ClinicalRecordStatus.signed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El expediente clinico es inmutable una vez firmado (RN-21)")
    old = model_to_dict(record)
    update_payload = data_for_model(data, ClinicalRecord)
    update_payload.pop("id", None)  # data_for_model auto-generates an id for create paths; never apply it on update
    for key, value in update_payload.items():
        setattr(record, key, value)
    audit(db, user_id=user_id, tenant_id=tenant_id, action="UPDATE", table_name="clinical_records", record_id=record.id, old_values=old, new_values=model_to_dict(record))
    commit_or_409(db)
    db.refresh(record)
    return record


def verify_primary_diagnosis(db: Session, clinical_record_id: bytes) -> bool:
    count = db.query(RecordDiagnosis).filter(RecordDiagnosis.clinical_record_id == clinical_record_id, RecordDiagnosis.is_primary_diagnosis.is_(True)).count()
    return count == 1


def sign_clinical_record(db: Session, record_id: bytes, tenant_id: str, signature: str, doctor: User) -> ClinicalRecord:
    if doctor.role != UserRole.doctor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo los medicos pueden firmar expedientes clinicos")
    record = get_clinical_record(db, record_id, tenant_id)
    if record.status == ClinicalRecordStatus.signed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El expediente clinico ya esta firmado.")
    if not verify_primary_diagnosis(db, record.id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Firmar requiere exactamente un diagnostico primario (RN-24)")
    old = model_to_dict(record)
    record.status = ClinicalRecordStatus.signed
    record.signed_at = datetime.now(timezone.utc)
    record.digital_signature = signature
    audit(db, user_id=doctor.id, tenant_id=tenant_id, action="SIGN", table_name="clinical_records", record_id=record.id, old_values=old, new_values=model_to_dict(record))
    commit_or_409(db)
    db.refresh(record)
    return record


def add_correction_note(db: Session, record_id: bytes, tenant_id: str, note_text: str, user_id: bytes) -> ClinicalNote:
    record = get_clinical_record(db, record_id, tenant_id)
    note = ClinicalNote(
        id=new_uuid_bytes(),
        patient_id=record.patient_id,
        tenant_id=tenant_id,
        clinical_record_id=record_id,
        note_type=NoteType.other,
        content=note_text,
        authored_by=user_id,
    )
    db.add(note)
    db.flush()
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="clinical_notes", record_id=note.id, new_values=model_to_dict(note))
    commit_or_409(db)
    db.refresh(note)
    return note
