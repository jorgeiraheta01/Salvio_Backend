from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.db import get_db
from app.models.clinical import (
    ClinicalNote,
    ClinicalProblem,
    ClinicalProcedure,
    ClinicalRecord,
    ClinicalRecordStatus,
    ClinicalScaleResult,
    NoteType,
    PhysicalExamFinding,
    RecordDiagnosis,
    RecordPlan,
    ReviewOfSystem,
    VitalSign,
)
from app.models.patient import Patient
from app.models.tenant import User, UserRole
from app.routers._utils import audit_mutation, commit_or_409, data_for_create, data_for_model, ensure_patient_exists, get_by_id_or_404, model_to_dict
from app.schemas.clinical import (
    ClinicalNoteCreate,
    ClinicalNoteRead,
    ClinicalProblemCreate,
    ClinicalProblemRead,
    ClinicalProcedureCreate,
    ClinicalProcedureRead,
    ClinicalRecordCreate,
    ClinicalRecordDetail,
    ClinicalRecordRead,
    ClinicalRecordSignRequest,
    ClinicalRecordUpdate,
    ClinicalScaleResultCreate,
    ClinicalScaleResultRead,
    CorrectionNoteCreate,
    PhysicalExamFindingCreate,
    PhysicalExamFindingRead,
    RecordDiagnosisCreate,
    RecordDiagnosisRead,
    RecordPlanCreate,
    RecordPlanRead,
    ReviewOfSystemCreate,
    ReviewOfSystemRead,
    VitalSignCreate,
    VitalSignRead,
)
from app.services.clinical_service import add_correction_note as svc_add_correction_note
from app.services.clinical_service import create_clinical_record as svc_create_clinical_record
from app.services.clinical_service import get_clinical_record as svc_get_clinical_record
from app.services.clinical_service import sign_clinical_record as svc_sign_clinical_record
from app.services.clinical_service import update_clinical_record as svc_update_clinical_record
from app.services.vital_signs_service import create_vital_sign as svc_create_vital_sign

router = APIRouter(prefix="/api/v1/clinical-records", tags=["Clinical Records"])
CLINICAL_EDIT_ROLES = (UserRole.doctor, UserRole.resident)


def _record_or_404(db: Session, record_id: UUID, tenant_id: str) -> ClinicalRecord:
    return get_by_id_or_404(db, ClinicalRecord, record_id, tenant_id)


def _ensure_draft(record: ClinicalRecord) -> None:
    if record.status == ClinicalRecordStatus.signed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Signed clinical records are immutable.")


def _detail(db: Session, record: ClinicalRecord) -> dict[str, Any]:
    record_id = record.id
    data = model_to_dict(record)
    data["vital_signs"] = db.query(VitalSign).filter(VitalSign.clinical_record_id == record_id, VitalSign.tenant_id == record.tenant_id).all()
    data["diagnoses"] = db.query(RecordDiagnosis).filter(RecordDiagnosis.clinical_record_id == record_id, RecordDiagnosis.tenant_id == record.tenant_id).all()
    data["physical_exam_findings"] = db.query(PhysicalExamFinding).filter(PhysicalExamFinding.clinical_record_id == record_id, PhysicalExamFinding.tenant_id == record.tenant_id).all()
    data["review_of_systems"] = db.query(ReviewOfSystem).filter(ReviewOfSystem.clinical_record_id == record_id, ReviewOfSystem.tenant_id == record.tenant_id).all()
    data["plans"] = db.query(RecordPlan).filter(RecordPlan.clinical_record_id == record_id, RecordPlan.tenant_id == record.tenant_id).all()
    data["notes"] = db.query(ClinicalNote).filter(ClinicalNote.clinical_record_id == record_id, ClinicalNote.tenant_id == record.tenant_id).all()
    data["scales"] = db.query(ClinicalScaleResult).filter(ClinicalScaleResult.clinical_record_id == record_id, ClinicalScaleResult.tenant_id == record.tenant_id).all()
    return data


@router.post("", response_model=ClinicalRecordRead, status_code=status.HTTP_201_CREATED)
def create_clinical_record(
    data: ClinicalRecordCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*CLINICAL_EDIT_ROLES)),
):
    return svc_create_clinical_record(db, current_user.tenant_id, data, current_user)


@router.get("/{record_id}", response_model=ClinicalRecordDetail)
def get_clinical_record(record_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _detail(db, _record_or_404(db, record_id, current_user.tenant_id))


@router.patch("/{record_id}", response_model=ClinicalRecordRead)
def update_clinical_record(
    record_id: UUID,
    data: ClinicalRecordUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*CLINICAL_EDIT_ROLES)),
):
    return svc_update_clinical_record(db, record_id.bytes, current_user.tenant_id, data, current_user.id)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_clinical_record(
    record_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*CLINICAL_EDIT_ROLES)),
):
    record = _record_or_404(db, record_id, current_user.tenant_id)
    _ensure_draft(record)
    old = model_to_dict(record)
    record.deleted_at = datetime.now(timezone.utc)
    audit_mutation(db, request, current_user, action="soft_delete", table_name="clinical_records", record_id=record.id, old_values=old, new_values=model_to_dict(record))
    commit_or_409(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{record_id}/sign", response_model=ClinicalRecordRead)
def sign_clinical_record(
    record_id: UUID,
    data: ClinicalRecordSignRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor)),
):
    return svc_sign_clinical_record(db, record_id.bytes, current_user.tenant_id, data.digital_signature, current_user)


@router.post("/{record_id}/correction-notes", response_model=ClinicalNoteRead, status_code=status.HTTP_201_CREATED)
def create_correction_note(
    record_id: UUID,
    data: CorrectionNoteCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor)),
):
    return svc_add_correction_note(db, record_id.bytes, current_user.tenant_id, data.note_text, current_user.id)


def _create_record_child(db: Session, request: Request, current_user: User, record_id: UUID, model: Any, data: Any, *, exclude: set[str] | None = None):
    record = _record_or_404(db, record_id, current_user.tenant_id)
    _ensure_draft(record)
    payload = data_for_create(data, model, exclude=exclude or set(), tenant_id=current_user.tenant_id)
    if "clinical_record_id" in model.__table__.columns:
        payload["clinical_record_id"] = record.id
    if "patient_id" in model.__table__.columns and "patient_id" not in payload:
        payload["patient_id"] = record.patient_id
    obj = model(**payload)
    db.add(obj)
    db.flush()
    audit_mutation(db, request, current_user, action="create", table_name=model.__tablename__, record_id=obj.id, new_values=model_to_dict(obj))
    commit_or_409(db)
    db.refresh(obj)
    return obj


def _list_record_children(db: Session, current_user: User, record_id: UUID, model: Any):
    record = _record_or_404(db, record_id, current_user.tenant_id)
    return db.query(model).filter(model.clinical_record_id == record.id, model.tenant_id == current_user.tenant_id).all()


def _subresource(path: str, model: Any, create_schema: Any, read_schema: Any, *, exclude: set[str] | None = None):
    @router.get(f"/{{record_id}}/{path}", response_model=list[read_schema])
    def list_endpoint(
        record_id: UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        return _list_record_children(db, current_user, record_id, model)

    @router.post(f"/{{record_id}}/{path}", response_model=read_schema, status_code=status.HTTP_201_CREATED)
    def create_endpoint(
        record_id: UUID,
        data: create_schema,
        request: Request,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_roles(*CLINICAL_EDIT_ROLES)),
    ):
        if model is VitalSign:
            data = data.model_copy(update={"clinical_record_id": record_id})
            vital, _alert = svc_create_vital_sign(db, current_user.tenant_id, data, current_user.id)
            return vital
        return _create_record_child(db, request, current_user, record_id, model, data, exclude=exclude)


@router.get("/{record_id}/diagnoses", response_model=list[RecordDiagnosisRead])
def list_record_diagnoses(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _list_record_children(db, current_user, record_id, RecordDiagnosis)


@router.post("/{record_id}/diagnoses", response_model=RecordDiagnosisRead, status_code=status.HTTP_201_CREATED)
def create_record_diagnosis(
    record_id: UUID,
    data: RecordDiagnosisCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*CLINICAL_EDIT_ROLES)),
):
    record = _record_or_404(db, record_id, current_user.tenant_id)
    _ensure_draft(record)
    if data.is_primary_diagnosis:
        existing_primary = (
            db.query(RecordDiagnosis)
            .filter(
                RecordDiagnosis.clinical_record_id == record.id,
                RecordDiagnosis.tenant_id == current_user.tenant_id,
                RecordDiagnosis.is_primary_diagnosis.is_(True),
            )
            .first()
        )
        if existing_primary:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only one primary diagnosis is allowed per clinical record.")
    return _create_record_child(db, request, current_user, record_id, RecordDiagnosis, data)


_subresource("vital-signs", VitalSign, VitalSignCreate, VitalSignRead, exclude={"alert", "bmi_calculated"})
_subresource("physical-exam-findings", PhysicalExamFinding, PhysicalExamFindingCreate, PhysicalExamFindingRead)
_subresource("review-of-systems", ReviewOfSystem, ReviewOfSystemCreate, ReviewOfSystemRead)
_subresource("clinical-problems", ClinicalProblem, ClinicalProblemCreate, ClinicalProblemRead)
_subresource("plans", RecordPlan, RecordPlanCreate, RecordPlanRead)
_subresource("notes", ClinicalNote, ClinicalNoteCreate, ClinicalNoteRead)
_subresource("scales", ClinicalScaleResult, ClinicalScaleResultCreate, ClinicalScaleResultRead, exclude={"alert"})
_subresource("procedures", ClinicalProcedure, ClinicalProcedureCreate, ClinicalProcedureRead)
