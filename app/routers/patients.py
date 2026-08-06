from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.db import get_db
from app.dependencies.module_gate import require_module
from app.models.development import PatientDevelopmentRecord
from app.models.patient import (
    Patient,
    PatientAllergy,
    PatientChronicDisease,
    PatientConsent,
    PatientDevelopmentHx,
    PatientFamilyHx,
    PatientGrowthMeasurement,
    PatientGynecologicalHx,
    PatientHospitalizationHx,
    PatientImmunization,
    PatientMedication,
    PatientPerinatalHx,
    PatientPhysiologicalHx,
    PatientSocialHx,
    PatientSurgery,
)
from app.models.tenant import User, UserRole
from app.routers._utils import (
    audit_mutation,
    commit_or_409,
    data_for_model,
    data_for_create,
    ensure_patient_exists,
    get_by_id_or_404,
    model_to_dict,
    next_mrn,
    patient_search_filter,
    uuid_bytes,
)
from app.schemas.common import PaginatedResponse
from app.schemas.patient import (
    PatientAllergyCreate,
    PatientAllergyRead,
    PatientChronicDiseaseCreate,
    PatientChronicDiseaseRead,
    PatientConsentCreate,
    PatientConsentRead,
    PatientCreate,
    PatientDevelopmentHxCreate,
    PatientDevelopmentHxRead,
    PatientDevelopmentRecordCreate,
    PatientDevelopmentRecordRead,
    PatientFamilyHxCreate,
    PatientFamilyHxRead,
    PatientGrowthMeasurementCreate,
    PatientGrowthMeasurementRead,
    PatientGynecologicalHxCreate,
    PatientGynecologicalHxRead,
    PatientHospitalizationHxCreate,
    PatientHospitalizationHxRead,
    PatientImmunizationCreate,
    PatientImmunizationRead,
    PatientMedicationCreate,
    PatientMedicationRead,
    PatientPerinatalHxCreate,
    PatientPerinatalHxRead,
    PatientPhysiologicalHxCreate,
    PatientPhysiologicalHxRead,
    PatientRead,
    PatientSocialHxCreate,
    PatientSocialHxRead,
    PatientSurgeryCreate,
    PatientSurgeryRead,
    PatientUpdate,
)
from app.services.patient_service import create_patient as svc_create_patient
from app.services.patient_service import get_patient as svc_get_patient
from app.services.patient_service import search_patients as svc_search_patients
from app.services.patient_service import soft_delete_patient as svc_soft_delete_patient
from app.services.patient_service import update_patient as svc_update_patient

router = APIRouter(prefix="/api/v1/patients", tags=["Patients"], dependencies=[Depends(require_module("pacientes"))])
PATIENT_ROLES = (UserRole.clinic_admin, UserRole.doctor, UserRole.resident, UserRole.nurse, UserRole.receptionist)


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient(
    data: PatientCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*PATIENT_ROLES)),
):
    return svc_create_patient(db, current_user.tenant_id, data, current_user.id)


@router.get("", response_model=PaginatedResponse[PatientRead])
def list_patients(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data, total = svc_search_patients(db, current_user.tenant_id, q, page, limit)
    return {"data": data, "total": total, "page": page, "limit": limit}


@router.get("/{patient_id}", response_model=PatientRead)
def get_patient(patient_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return svc_get_patient(db, patient_id.bytes, current_user.tenant_id)


@router.patch("/{patient_id}", response_model=PatientRead)
def update_patient(
    patient_id: UUID,
    data: PatientUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*PATIENT_ROLES)),
):
    return svc_update_patient(db, patient_id.bytes, current_user.tenant_id, data, current_user.id)


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(
    patient_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.clinic_admin, UserRole.doctor, UserRole.receptionist)),
):
    svc_soft_delete_patient(db, patient_id.bytes, current_user.tenant_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _list_child(db: Session, model: Any, patient_id: UUID, tenant_id: str):
    ensure_patient_exists(db, Patient, patient_id, tenant_id)
    return db.query(model).filter(model.patient_id == uuid_bytes(patient_id), model.tenant_id == tenant_id).all()


def _create_child(db: Session, request: Request, current_user: User, model: Any, data: Any, patient_id: UUID):
    ensure_patient_exists(db, Patient, patient_id, current_user.tenant_id)
    payload = data_for_create(data, model, tenant_id=current_user.tenant_id)
    payload["patient_id"] = uuid_bytes(patient_id)
    obj = model(**payload)
    db.add(obj)
    db.flush()
    audit_mutation(db, request, current_user, action="create", table_name=model.__tablename__, record_id=obj.id, new_values=model_to_dict(obj))
    commit_or_409(db)
    db.refresh(obj)
    return obj


def _child_routes(path: str, model: Any, create_schema: Any, read_schema: Any):
    @router.get(f"/{{patient_id}}/{path}", response_model=list[read_schema])
    def list_endpoint(patient_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
        return _list_child(db, model, patient_id, current_user.tenant_id)

    @router.post(f"/{{patient_id}}/{path}", response_model=read_schema, status_code=status.HTTP_201_CREATED)
    def create_endpoint(
        patient_id: UUID,
        data: create_schema,
        request: Request,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_roles(*PATIENT_ROLES)),
    ):
        return _create_child(db, request, current_user, model, data, patient_id)


_child_routes("allergies", PatientAllergy, PatientAllergyCreate, PatientAllergyRead)
_child_routes("medications", PatientMedication, PatientMedicationCreate, PatientMedicationRead)
_child_routes("physiological-hx", PatientPhysiologicalHx, PatientPhysiologicalHxCreate, PatientPhysiologicalHxRead)
_child_routes("chronic-diseases", PatientChronicDisease, PatientChronicDiseaseCreate, PatientChronicDiseaseRead)
_child_routes("surgeries", PatientSurgery, PatientSurgeryCreate, PatientSurgeryRead)
_child_routes("hospitalizations-hx", PatientHospitalizationHx, PatientHospitalizationHxCreate, PatientHospitalizationHxRead)
_child_routes("family-hx", PatientFamilyHx, PatientFamilyHxCreate, PatientFamilyHxRead)
_child_routes("gynecological-hx", PatientGynecologicalHx, PatientGynecologicalHxCreate, PatientGynecologicalHxRead)
_child_routes("social-hx", PatientSocialHx, PatientSocialHxCreate, PatientSocialHxRead)
_child_routes("perinatal-hx", PatientPerinatalHx, PatientPerinatalHxCreate, PatientPerinatalHxRead)
_child_routes("development-hx", PatientDevelopmentHx, PatientDevelopmentHxCreate, PatientDevelopmentHxRead)
_child_routes("development-records", PatientDevelopmentRecord, PatientDevelopmentRecordCreate, PatientDevelopmentRecordRead)
_child_routes("consents", PatientConsent, PatientConsentCreate, PatientConsentRead)
_child_routes("immunizations", PatientImmunization, PatientImmunizationCreate, PatientImmunizationRead)
_child_routes("growth-measurements", PatientGrowthMeasurement, PatientGrowthMeasurementCreate, PatientGrowthMeasurementRead)
