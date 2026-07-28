from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.db import get_db
from app.models.encounter import ClinicalOrder
from app.models.tenant import User, UserRole
from app.routers._utils import audit_mutation, commit_or_409, model_to_dict
from app.schemas.encounter import EncounterOrderCreate, EncounterOrderRead
from app.services._utils import new_uuid_bytes
from app.services.encounter_service import ensure_encounter_editable, ensure_encounter_owner, get_encounter_or_404, resolve_request_tenant

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])


@router.get("", response_model=list[EncounterOrderRead])
def list_orders(
    encounter_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    encounter = get_encounter_or_404(db, encounter_id, current_user.tenant_id)
    return db.query(ClinicalOrder).filter(ClinicalOrder.encounter_id == encounter.id, ClinicalOrder.tenant_id == current_user.tenant_id).order_by(ClinicalOrder.created_at.asc()).all()


@router.post("", response_model=EncounterOrderRead, status_code=status.HTTP_201_CREATED)
def create_order(
    data: EncounterOrderCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    tenant_id = resolve_request_tenant(request, current_user)
    encounter = get_encounter_or_404(db, data.encounter_id, tenant_id)
    ensure_encounter_owner(encounter, current_user)
    ensure_encounter_editable(encounter)
    order = ClinicalOrder(
        id=new_uuid_bytes(),
        encounter_id=encounter.id,
        patient_id=encounter.patient_id,
        tenant_id=tenant_id,
        ordered_by=current_user.id,
        order_type=data.order_type,
        description=data.description,
        scheduled_for=data.scheduled_for,
        notes=data.notes,
        created_by=current_user.id,
        updated_by=current_user.id,
        version=1,
    )
    db.add(order)
    encounter.updated_by = current_user.id
    audit_mutation(db, request, current_user, action="create", table_name="clinical_orders", record_id=order.id, new_values=model_to_dict(order))
    commit_or_409(db)
    db.refresh(order)
    return order
