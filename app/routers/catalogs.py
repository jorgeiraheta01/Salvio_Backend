from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.db import get_db
from app.models.tenant import User, UserRole
from app.schemas.catalogs import (
    ClinicalSystemCatalogCreate,
    ClinicalSystemCatalogRead,
    ClinicalSystemCatalogUpdate,
    LabTestCatalogCreate,
    LabTestCatalogRead,
    LabTestCatalogUpdate,
    MedicationCatalogCreate,
    MedicationCatalogRead,
    MedicationCatalogUpdate,
)
from app.services.catalog_service import (
    create_clinical_system as svc_create_clinical_system,
    create_lab_test as svc_create_lab_test,
    create_medication as svc_create_medication,
    list_clinical_systems as svc_list_clinical_systems,
    list_lab_tests as svc_list_lab_tests,
    list_medications as svc_list_medications,
    update_clinical_system as svc_update_clinical_system,
    update_lab_test as svc_update_lab_test,
    update_medication as svc_update_medication,
)

router = APIRouter(prefix="/api/v1/catalogs", tags=["Catalogs"])


@router.get("/medications", response_model=list[MedicationCatalogRead])
def list_medications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return svc_list_medications(db, current_user.tenant_id)


@router.post("/medications", response_model=MedicationCatalogRead, status_code=201)
def create_medication(
    data: MedicationCatalogCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.clinic_admin)),
):
    return svc_create_medication(db, current_user.tenant_id, data, current_user.id)


@router.patch("/medications/{item_id}", response_model=MedicationCatalogRead)
def update_medication(
    item_id: UUID,
    data: MedicationCatalogUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.clinic_admin)),
):
    return svc_update_medication(db, item_id.bytes, current_user.tenant_id, data, current_user.id)


@router.get("/lab-tests", response_model=list[LabTestCatalogRead])
def list_lab_tests(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return svc_list_lab_tests(db)


@router.post("/lab-tests", response_model=LabTestCatalogRead, status_code=201)
def create_lab_test(
    data: LabTestCatalogCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.clinic_admin)),
):
    return svc_create_lab_test(db, current_user.tenant_id, data, current_user.id)


@router.patch("/lab-tests/{item_id}", response_model=LabTestCatalogRead)
def update_lab_test(
    item_id: UUID,
    data: LabTestCatalogUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.clinic_admin)),
):
    return svc_update_lab_test(db, item_id.bytes, current_user.tenant_id, data, current_user.id)


@router.get("/clinical-systems", response_model=list[ClinicalSystemCatalogRead])
def list_clinical_systems(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return svc_list_clinical_systems(db)


@router.post("/clinical-systems", response_model=ClinicalSystemCatalogRead, status_code=201)
def create_clinical_system(
    data: ClinicalSystemCatalogCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.clinic_admin)),
):
    return svc_create_clinical_system(db, current_user.tenant_id, data, current_user.id)


@router.patch("/clinical-systems/{item_id}", response_model=ClinicalSystemCatalogRead)
def update_clinical_system(
    item_id: UUID,
    data: ClinicalSystemCatalogUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.clinic_admin)),
):
    return svc_update_clinical_system(db, item_id.bytes, current_user.tenant_id, data, current_user.id)
