from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.db import get_db
from app.models.clinical import DiagnosisSeverity, DiagnosisStatus, DiagnosisType, RecordDiagnosis
from app.models.tenant import User, UserRole
from app.routers._utils import audit_mutation, commit_or_409, get_by_id_or_404, model_to_dict, uuid_bytes
from app.schemas.encounter import EncounterDiagnosisCreate, EncounterDiagnosisRead, EncounterDiagnosisUpdate
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
        status=diagnosis.status.value,
        severity=diagnosis.severity.value if diagnosis.severity else None,
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
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Solo se permite un diagnostico primario por encuentro.")
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
        status=DiagnosisStatus(data.status),
        severity=DiagnosisSeverity(data.severity) if data.severity else None,
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


def _get_diagnosis_for_edit(db: Session, diagnosis_id: UUID, request: Request, current_user: User) -> tuple[RecordDiagnosis, str]:
    tenant_id = resolve_request_tenant(request, current_user)
    diagnosis = get_by_id_or_404(db, RecordDiagnosis, diagnosis_id, tenant_id)
    encounter = get_encounter_or_404(db, UUID(bytes=diagnosis.encounter_id), tenant_id)
    ensure_encounter_owner(encounter, current_user)
    ensure_encounter_editable(encounter)
    return diagnosis, tenant_id


@router.patch("/{diagnosis_id}", response_model=EncounterDiagnosisRead)
def update_diagnosis(
    diagnosis_id: UUID,
    data: EncounterDiagnosisUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    diagnosis, tenant_id = _get_diagnosis_for_edit(db, diagnosis_id, request, current_user)
    old_values = model_to_dict(diagnosis)
    payload = data.model_dump(exclude_unset=True)

    if "classification" in payload:
        is_primary, is_background = _classification_to_flags(payload.pop("classification"))
        if is_primary and not diagnosis.is_primary_diagnosis:
            existing_primary = (
                db.query(RecordDiagnosis)
                .filter(
                    RecordDiagnosis.encounter_id == diagnosis.encounter_id,
                    RecordDiagnosis.tenant_id == tenant_id,
                    RecordDiagnosis.is_primary_diagnosis.is_(True),
                    RecordDiagnosis.id != diagnosis.id,
                )
                .first()
            )
            if existing_primary:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Solo se permite un diagnostico primario por encuentro.")
        diagnosis.is_primary_diagnosis = is_primary
        diagnosis.is_background = is_background
    if "type" in payload:
        diagnosis.diagnosis_type = _type_to_enum(payload.pop("type"))
    if "status" in payload:
        diagnosis.status = DiagnosisStatus(payload.pop("status"))
    if "severity" in payload:
        severity_value = payload.pop("severity")
        diagnosis.severity = DiagnosisSeverity(severity_value) if severity_value else None
    if "notes" in payload:
        diagnosis.notes = payload.pop("notes")

    diagnosis.updated_by = current_user.id
    diagnosis.version += 1
    audit_mutation(db, request, current_user, action="update", table_name="record_diagnoses", record_id=diagnosis.id, old_values=old_values, new_values=model_to_dict(diagnosis))
    commit_or_409(db)
    db.refresh(diagnosis)
    return _to_read(diagnosis)


@router.delete("/{diagnosis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_diagnosis(
    diagnosis_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    diagnosis, _ = _get_diagnosis_for_edit(db, diagnosis_id, request, current_user)
    old_values = model_to_dict(diagnosis)
    audit_mutation(db, request, current_user, action="delete", table_name="record_diagnoses", record_id=diagnosis.id, old_values=old_values)
    db.delete(diagnosis)
    commit_or_409(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
