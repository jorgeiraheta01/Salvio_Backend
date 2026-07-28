from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.db import get_db
from app.models.clinical import DiagnosisType, RecordDiagnosis
from app.models.tenant import User, UserRole
from app.routers._utils import audit_mutation, commit_or_409, model_to_dict, uuid_bytes
from app.schemas.encounter import EncounterDiagnosisCreate, EncounterDiagnosisRead
from app.services._utils import new_uuid_bytes
from app.services.encounter_service import ensure_encounter_editable, ensure_encounter_owner, get_encounter_or_404, resolve_request_tenant

router = APIRouter(prefix="/api/v1/diagnoses", tags=["Diagnoses"])


def _classification_to_flags(classification: str) -> tuple[bool, bool]:
    is_primary = classification == "primary"
    is_background = classification == "background"
    return is_primary, is_background


def _type_to_enum(value: str) -> DiagnosisType:
    return DiagnosisType(value)


def _to_read(diagnosis: RecordDiagnosis) -> EncounterDiagnosisRead:
    classification = "primary" if diagnosis.is_primary_diagnosis else "background" if diagnosis.is_background else "secondary"
    return EncounterDiagnosisRead(
        id=UUID(bytes=diagnosis.id),
        encounter_id=UUID(bytes=diagnosis.encounter_id) if diagnosis.encounter_id else None,
        code=diagnosis.cie10_code,
        description=diagnosis.cie10_description,
        type=diagnosis.diagnosis_type.value,
        classification=classification,
        is_first_time=diagnosis.is_first_time,
        notes=diagnosis.notes,
        version=diagnosis.version,
        created_at=diagnosis.created_at,
        updated_at=diagnosis.updated_at,
    )


@router.get("", response_model=list[EncounterDiagnosisRead])
def list_diagnoses(
    encounter_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    encounter = get_encounter_or_404(db, encounter_id, current_user.tenant_id)
    diagnoses = (
        db.query(RecordDiagnosis)
        .filter(RecordDiagnosis.encounter_id == encounter.id, RecordDiagnosis.tenant_id == current_user.tenant_id)
        .order_by(RecordDiagnosis.created_at.asc())
        .all()
    )
    return [_to_read(item) for item in diagnoses]


@router.post("", response_model=EncounterDiagnosisRead, status_code=status.HTTP_201_CREATED)
def create_diagnosis(
    data: EncounterDiagnosisCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    tenant_id = resolve_request_tenant(request, current_user)
    encounter = get_encounter_or_404(db, data.encounter_id, tenant_id)
    ensure_encounter_owner(encounter, current_user)
    ensure_encounter_editable(encounter)
    is_primary, is_background = _classification_to_flags(data.classification)
    if is_primary:
        existing_primary = (
            db.query(RecordDiagnosis)
            .filter(
                RecordDiagnosis.encounter_id == encounter.id,
                RecordDiagnosis.tenant_id == tenant_id,
                RecordDiagnosis.is_primary_diagnosis.is_(True),
            )
            .first()
        )
        if existing_primary:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only one primary diagnosis is allowed per encounter.")
    diagnosis = RecordDiagnosis(
        id=new_uuid_bytes(),
        encounter_id=encounter.id,
        clinical_record_id=uuid_bytes(data.clinical_record_id) if data.clinical_record_id else None,
        tenant_id=tenant_id,
        cie10_code=data.code,
        cie10_description=data.description,
        diagnosis_type=_type_to_enum(data.type),
        is_first_time=data.is_first_time,
        is_primary_diagnosis=is_primary,
        is_background=is_background,
        is_outpatient=True,
        notes=data.notes,
        created_by=current_user.id,
        updated_by=current_user.id,
        version=1,
    )
    db.add(diagnosis)
    encounter.updated_by = current_user.id
    audit_mutation(db, request, current_user, action="create", table_name="record_diagnoses", record_id=diagnosis.id, new_values=model_to_dict(diagnosis))
    commit_or_409(db)
    db.refresh(diagnosis)
    return _to_read(diagnosis)
