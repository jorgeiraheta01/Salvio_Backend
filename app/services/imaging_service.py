from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.imaging import ImagingAttachment, ImagingReport, ImagingStatus, ImagingStudy
from app.models.patient import Patient
from app.schemas.imaging import ImagingAttachmentCreate, ImagingReportCreate, ImagingStudyCreate, ImagingStudyUpdate
from app.services._utils import audit, commit_or_409, data_for_model, model_to_dict, new_uuid_bytes, not_found

# H-04: mismo principio que lab -- nunca retrocede, cancelar es la unica
# salida desde un estado no terminal.
IMAGING_ALLOWED_TRANSITIONS = {
    ImagingStatus.ordered: {ImagingStatus.performed, ImagingStatus.cancelled},
    ImagingStatus.performed: {ImagingStatus.reviewed, ImagingStatus.cancelled},
    ImagingStatus.reviewed: set(),
    ImagingStatus.cancelled: set(),
}


def create_imaging_study(db: Session, tenant_id: str, data: ImagingStudyCreate, user_id: bytes) -> ImagingStudy:
    patient = db.query(Patient).filter(Patient.id == data.patient_id.bytes, Patient.tenant_id == tenant_id, Patient.deleted_at.is_(None)).first()
    if not patient:
        raise not_found("Patient not found.")
    study = ImagingStudy(**data_for_model(data, ImagingStudy, tenant_id=tenant_id))
    study.id = new_uuid_bytes()
    study.status = ImagingStatus.ordered
    db.add(study)
    db.flush()
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="imaging_studies", record_id=study.id, new_values=model_to_dict(study))
    commit_or_409(db)
    db.refresh(study)
    return study


def get_imaging_study(db: Session, study_id: bytes, tenant_id: str) -> ImagingStudy:
    study = db.query(ImagingStudy).filter(ImagingStudy.id == study_id, ImagingStudy.tenant_id == tenant_id).first()
    if not study:
        raise not_found("Imaging study not found.")
    return study


def update_imaging_status(db: Session, study_id: bytes, tenant_id: str, data: ImagingStudyUpdate, user_id: bytes) -> ImagingStudy:
    study = get_imaging_study(db, study_id, tenant_id)
    if data.status is not None and data.status != study.status:
        if data.status not in IMAGING_ALLOWED_TRANSITIONS[study.status]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No se puede pasar el estudio de imagenologia de '{study.status.value}' a '{data.status.value}'",
            )
    old = model_to_dict(study)
    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(study, field, value)
    audit(db, user_id=user_id, tenant_id=tenant_id, action="UPDATE", table_name="imaging_studies", record_id=study.id, old_values=old, new_values=model_to_dict(study))
    commit_or_409(db)
    db.refresh(study)
    return study


def add_imaging_report(db: Session, study_id: bytes, tenant_id: str, data: ImagingReportCreate, user_id: bytes) -> ImagingReport:
    study = get_imaging_study(db, study_id, tenant_id)
    old = model_to_dict(study)
    report = ImagingReport(**data_for_model(data, ImagingReport, tenant_id=tenant_id))
    report.id = new_uuid_bytes()
    report.imaging_study_id = study_id
    study.status = ImagingStatus.reviewed
    db.add(report)
    db.flush()
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="imaging_reports", record_id=report.id, new_values=model_to_dict(report))
    audit(db, user_id=user_id, tenant_id=tenant_id, action="UPDATE", table_name="imaging_studies", record_id=study.id, old_values=old, new_values=model_to_dict(study))
    commit_or_409(db)
    db.refresh(report)
    return report


def add_imaging_attachment(db: Session, study_id: bytes, tenant_id: str, data: ImagingAttachmentCreate, user_id: bytes) -> ImagingAttachment:
    get_imaging_study(db, study_id, tenant_id)
    attachment = ImagingAttachment(**data_for_model(data, ImagingAttachment, tenant_id=tenant_id))
    attachment.id = new_uuid_bytes()
    attachment.imaging_study_id = study_id
    db.add(attachment)
    db.flush()
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="imaging_attachments", record_id=attachment.id, new_values=model_to_dict(attachment))
    commit_or_409(db)
    db.refresh(attachment)
    return attachment
