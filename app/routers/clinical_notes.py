from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.db import get_db
from app.models.clinical import ClinicalNote
from app.models.encounter import EncounterStatus
from app.models.tenant import User, UserRole
from app.routers._utils import audit_mutation, commit_or_409, model_to_dict
from app.schemas.encounter import EncounterClinicalNoteClose, EncounterClinicalNoteCreate, EncounterClinicalNoteRead, EncounterClinicalNoteUpdate
from app.services.encounter_service import ensure_encounter_editable, ensure_encounter_owner, ensure_version, get_encounter_or_404, resolve_request_tenant
from app.services._utils import new_uuid_bytes

router = APIRouter(prefix="/api/v1/clinical-notes", tags=["Clinical Notes"])


@router.get("", response_model=list[EncounterClinicalNoteRead])
def list_clinical_notes(
    encounter_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    encounter = get_encounter_or_404(db, encounter_id, current_user.tenant_id)
    return db.query(ClinicalNote).filter(ClinicalNote.encounter_id == encounter.id, ClinicalNote.tenant_id == current_user.tenant_id).order_by(ClinicalNote.created_at.desc()).all()


@router.post("", response_model=EncounterClinicalNoteRead, status_code=status.HTTP_201_CREATED)
def create_clinical_note(
    data: EncounterClinicalNoteCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    tenant_id = resolve_request_tenant(request, current_user)
    encounter = get_encounter_or_404(db, data.encounter_id, tenant_id)
    ensure_encounter_owner(encounter, current_user)
    ensure_encounter_editable(encounter)
    note = ClinicalNote(
        id=new_uuid_bytes(),
        patient_id=encounter.patient_id,
        tenant_id=tenant_id,
        encounter_id=encounter.id,
        note_type=data.note_type,
        content=data.content,
        authored_by=current_user.id,
        authored_by_name=current_user.full_name,
        updated_by=current_user.id,
        version=1,
    )
    db.add(note)
    encounter.updated_by = current_user.id
    audit_mutation(db, request, current_user, action="create", table_name="clinical_notes", record_id=note.id, new_values=model_to_dict(note))
    commit_or_409(db)
    db.refresh(note)
    return note


@router.patch("/{note_id}", response_model=EncounterClinicalNoteRead)
def update_clinical_note(
    note_id: UUID,
    data: EncounterClinicalNoteUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    tenant_id = resolve_request_tenant(request, current_user)
    note = db.query(ClinicalNote).filter(ClinicalNote.id == note_id.bytes, ClinicalNote.tenant_id == tenant_id).first()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinical note not found.")
    encounter = get_encounter_or_404(db, note.encounter_id, tenant_id)
    ensure_encounter_owner(encounter, current_user)
    ensure_encounter_editable(encounter)
    if note.is_closed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Closed clinical notes are immutable.")
    ensure_version(data.version, note.version)
    old = model_to_dict(note)
    note.content = data.content
    note.updated_by = current_user.id
    note.version += 1
    encounter.updated_by = current_user.id
    audit_mutation(db, request, current_user, action="update", table_name="clinical_notes", record_id=note.id, old_values=old, new_values=model_to_dict(note))
    commit_or_409(db)
    db.refresh(note)
    return note


@router.post("/{note_id}/close", response_model=EncounterClinicalNoteRead)
def close_clinical_note(
    note_id: UUID,
    data: EncounterClinicalNoteClose,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    tenant_id = resolve_request_tenant(request, current_user)
    note = db.query(ClinicalNote).filter(ClinicalNote.id == note_id.bytes, ClinicalNote.tenant_id == tenant_id).first()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinical note not found.")
    encounter = get_encounter_or_404(db, note.encounter_id, tenant_id)
    ensure_encounter_owner(encounter, current_user)
    ensure_encounter_editable(encounter)
    ensure_version(data.version, note.version)
    old = model_to_dict(note)
    note.is_closed = True
    note.closed_at = datetime.now(timezone.utc)
    note.updated_by = current_user.id
    note.version += 1
    if encounter.status == EncounterStatus.active:
        encounter.status = EncounterStatus.completed
        encounter.completed_at = datetime.now(timezone.utc)
        encounter.updated_by = current_user.id
    audit_mutation(db, request, current_user, action="close", table_name="clinical_notes", record_id=note.id, old_values=old, new_values=model_to_dict(note))
    commit_or_409(db)
    db.refresh(note)
    return note
