from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.db import get_db
from app.models.imaging import ImagingReport, ImagingStudy
from app.models.tenant import User, UserRole
from app.routers._utils import audit_mutation, commit_or_409, data_for_create, data_for_model, get_by_id_or_404, model_to_dict, uuid_bytes
from app.schemas.imaging import ImagingReportCreate, ImagingReportRead, ImagingStudyCreate, ImagingStudyDetail, ImagingStudyRead, ImagingStudyUpdate
from app.services.imaging_service import add_imaging_report as svc_add_imaging_report
from app.services.imaging_service import create_imaging_study as svc_create_imaging_study
from app.services.imaging_service import get_imaging_study as svc_get_imaging_study
from app.services.imaging_service import update_imaging_status as svc_update_imaging_status

router = APIRouter(prefix="/api/v1/imaging-studies", tags=["Imaging"])


@router.post("", response_model=ImagingStudyRead, status_code=status.HTTP_201_CREATED)
def create_imaging_study(
    data: ImagingStudyCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    return svc_create_imaging_study(db, current_user.tenant_id, data, current_user.id)


@router.get("", response_model=list[ImagingStudyRead])
def list_imaging_studies(
    patient_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ImagingStudy).filter(ImagingStudy.tenant_id == current_user.tenant_id)
    if patient_id:
        query = query.filter(ImagingStudy.patient_id == uuid_bytes(patient_id))
    return query.order_by(ImagingStudy.order_datetime.desc()).all()


@router.get("/{study_id}", response_model=ImagingStudyDetail)
def get_imaging_study(study_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    study = svc_get_imaging_study(db, study_id.bytes, current_user.tenant_id)
    data = model_to_dict(study)
    data["reports"] = db.query(ImagingReport).filter(ImagingReport.imaging_study_id == study.id, ImagingReport.tenant_id == current_user.tenant_id).all()
    data["attachments"] = []
    return data


@router.patch("/{study_id}/status", response_model=ImagingStudyRead)
def update_imaging_status(
    study_id: UUID,
    data: ImagingStudyUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    return svc_update_imaging_status(db, study_id.bytes, current_user.tenant_id, data, current_user.id)


@router.post("/{study_id}/reports", response_model=ImagingReportRead, status_code=status.HTTP_201_CREATED)
def create_imaging_report(
    study_id: UUID,
    data: ImagingReportCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    return svc_add_imaging_report(db, study_id.bytes, current_user.tenant_id, data, current_user.id)
