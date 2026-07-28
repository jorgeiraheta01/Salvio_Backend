from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.clinical import ClinicalNote, NoteType
from app.models.encounter import EncounterStatus
from app.models.prescription import Prescription, PrescriptionItem, PrescriptionStatus
from app.models.tenant import User
from app.services.encounter_service import ensure_encounter_editable, ensure_encounter_owner, get_encounter_or_404
from app.schemas.prescription import AllergyOverrideRequest, PrescriptionCreate
from app.services._utils import audit, commit_or_409, data_for_model, model_to_dict, new_uuid_bytes, not_found
from app.services.patient_service import check_allergy_alert


def create_prescription(db: Session, tenant_id: str, data: PrescriptionCreate, doctor: User) -> tuple[Prescription, list[dict]]:
    patient_id = data.patient_id.bytes if data.patient_id else None
    encounter_id = data.encounter_id.bytes if data.encounter_id else None
    if encounter_id is not None:
        encounter = get_encounter_or_404(db, encounter_id, tenant_id)
        ensure_encounter_owner(encounter, doctor)
        ensure_encounter_editable(encounter)
        patient_id = encounter.patient_id
    if patient_id is None:
        raise not_found("Patient not found.")
    medication_names = [item.medication_name for item in data.medications]
    for item in data.medications:
        if not item.dose or not item.frequency or not item.route:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Each prescription item requires dose, frequency and route.")
    allergy_alerts = check_allergy_alert(db, patient_id, medication_names)
    status_value = PrescriptionStatus.pending_override if allergy_alerts else PrescriptionStatus.active
    payload = data_for_model(data, Prescription, exclude={"medications", "known_allergy_alerts"}, tenant_id=tenant_id)
    payload["id"] = new_uuid_bytes()
    payload["patient_id"] = patient_id
    payload["encounter_id"] = encounter_id
    payload["status"] = status_value
    payload["prescribed_by"] = doctor.id
    payload["prescribed_by_name"] = doctor.full_name
    payload["updated_by"] = doctor.id
    prescription = Prescription(**payload)
    db.add(prescription)
    db.flush()
    for item in data.medications:
        item_payload = data_for_model(item, PrescriptionItem, exclude={"name"}, tenant_id=tenant_id)
        item_payload["id"] = new_uuid_bytes()
        item_payload["prescription_id"] = prescription.id
        db.add(PrescriptionItem(**item_payload))
    audit(db, user_id=doctor.id, tenant_id=tenant_id, action="INSERT", table_name="prescriptions", record_id=prescription.id, new_values=model_to_dict(prescription))
    commit_or_409(db)
    db.refresh(prescription)
    return prescription, allergy_alerts


def override_allergy(db: Session, prescription_id: bytes, tenant_id: str, data: AllergyOverrideRequest, user_id: bytes) -> None:
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id, Prescription.tenant_id == tenant_id).first()
    if not prescription:
        raise not_found("Prescription not found.")
    if prescription.status != PrescriptionStatus.pending_override:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Prescription is not pending an allergy override")
    old = model_to_dict(prescription)
    prescription.status = PrescriptionStatus.active
    prescription.updated_by = user_id
    prescription.version += 1
    note = ClinicalNote(
        id=new_uuid_bytes(),
        patient_id=prescription.patient_id,
        tenant_id=tenant_id,
        encounter_id=prescription.encounter_id,
        clinical_record_id=prescription.clinical_record_id,
        note_type=NoteType.other,
        content=f"Allergy override approved - {data.medication}: {data.override_reason}",
        authored_by=user_id,
    )
    db.add(note)
    db.flush()
    audit(db, user_id=user_id, tenant_id=tenant_id, action="UPDATE", table_name="prescriptions", record_id=prescription.id, old_values=old, new_values=model_to_dict(prescription))
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="clinical_notes", record_id=note.id, new_values=model_to_dict(note))
    commit_or_409(db)
