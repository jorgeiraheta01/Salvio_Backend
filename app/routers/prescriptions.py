from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.dependencies.auth import require_roles
from app.dependencies.db import get_db
from app.models.clinical import ClinicalNote, NoteType
from app.models.encounter import Encounter
from app.models.patient import PatientAllergy
from app.models.prescription import Prescription, PrescriptionItem, PrescriptionStatus
from app.models.tenant import User, UserRole
from app.routers._utils import audit_mutation, commit_or_409, data_for_create, data_for_model, get_by_id_or_404, model_to_dict
from app.schemas.prescription import AllergyAlert, AllergyOverrideRequest, AllergyOverrideResponse, PrescriptionCreate, PrescriptionCreateResponse, PrescriptionRead
from app.services.encounter_service import get_encounter_or_404, resolve_request_tenant
from app.services.prescription_service import create_prescription as svc_create_prescription
from app.services.prescription_service import override_allergy as svc_override_allergy

router = APIRouter(prefix="/api/v1/prescriptions", tags=["Prescriptions"])


def _allergy_alerts(db: Session, data: PrescriptionCreate, tenant_id: str) -> list[AllergyAlert]:
    allergies = (
        db.query(PatientAllergy)
        .filter(PatientAllergy.patient_id == data.patient_id.bytes, PatientAllergy.tenant_id == tenant_id, PatientAllergy.is_active.is_(True))
        .all()
    )
    alerts: list[AllergyAlert] = []
    for item in data.medications:
        med_name = item.medication_name.lower()
        for allergy in allergies:
            if allergy.allergen and allergy.allergen.lower() in med_name:
                alerts.append(
                    AllergyAlert(
                        medication=item.medication_name,
                        allergen=allergy.allergen,
                        severity=allergy.severity,
                        reaction=allergy.reaction,
                    )
                )
    return alerts


@router.post("", response_model=PrescriptionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_prescription(
    data: PrescriptionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    tenant_id = resolve_request_tenant(request, current_user)
    prescription, alerts = svc_create_prescription(db, tenant_id, data, current_user)
    return PrescriptionCreateResponse(
        id=prescription.id,
        allergy_alerts=alerts,
        status=prescription.status.value if hasattr(prescription.status, "value") else str(prescription.status),
        pdf_url=prescription.pdf_url,
    )


@router.get("", response_model=list[PrescriptionRead])
def list_prescriptions(
    encounter_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident, UserRole.nurse)),
):
    encounter = get_encounter_or_404(db, encounter_id, current_user.tenant_id)
    prescriptions = db.query(Prescription).filter(Prescription.encounter_id == encounter.id, Prescription.tenant_id == current_user.tenant_id).all()
    for item in prescriptions:
        item.items = db.query(PrescriptionItem).filter(PrescriptionItem.prescription_id == item.id, PrescriptionItem.tenant_id == current_user.tenant_id).all()
    return prescriptions


@router.post("/{prescription_id}/override-allergy", response_model=AllergyOverrideResponse)
def override_allergy(
    prescription_id: UUID,
    data: AllergyOverrideRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor)),
):
    svc_override_allergy(db, prescription_id.bytes, current_user.tenant_id, data, current_user.id)
    return AllergyOverrideResponse(id=prescription_id, override_recorded=True)
