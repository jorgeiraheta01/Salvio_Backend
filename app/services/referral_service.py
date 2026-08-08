import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_control_engine
from app.models.appointment import AdmissionStatus, PatientAdmission
from app.models.cross_tenant_referral import CrossTenantReferralIndex
from app.models.patient import Patient
from app.models.referral import PublicAccessToken, Referral, ReferralStatus, ReferralType
from app.models.tenant import Tenant, User
from app.schemas.referral import ReferralCreate, ReferralUpdate
from app.services._utils import audit, commit_or_409, data_for_model, model_to_dict, new_uuid_bytes, not_found

# H-04: pending es el unico estado desde el que se puede aceptar o rechazar;
# accepted solo avanza a completed; rejected/completed son terminales.
REFERRAL_ALLOWED_TRANSITIONS = {
    ReferralStatus.pending: {ReferralStatus.accepted, ReferralStatus.rejected},
    ReferralStatus.accepted: {ReferralStatus.completed},
    ReferralStatus.completed: set(),
    ReferralStatus.rejected: set(),
}


def create_referral(db: Session, tenant_id: str, data: ReferralCreate, user_id: bytes) -> Referral:
    referral = Referral(**data_for_model(data, Referral, tenant_id=tenant_id))
    referral.id = new_uuid_bytes()
    db.add(referral)
    db.flush()
    if referral.referral_type == ReferralType.public:
        generate_public_token(db, referral.id, referral.patient_id, referral.clinical_record_id)
    if referral.referral_type == ReferralType.cross_tenant:
        _index_cross_tenant_referral(db, tenant_id, referral)
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="referrals", record_id=referral.id, new_values=model_to_dict(referral))
    commit_or_409(db)
    db.refresh(referral)
    return referral


def _index_cross_tenant_referral(db: Session, tenant_id: str, referral: Referral) -> None:
    """Escribe un espejo minimo en el plano de control (salvio_control) para
    que el tenant destino pueda descubrir esta referencia -- no tiene acceso
    a la base de datos del tenant de origen para consultarla directamente."""
    patient = db.query(Patient).filter(Patient.id == referral.patient_id, Patient.tenant_id == tenant_id).first()
    patient_name = f"{patient.first_name} {patient.last_name}".strip() if patient else "Paciente desconocido"
    referring_doctor = db.query(User).filter(User.id == referral.referred_by, User.tenant_id == tenant_id).first() if referral.referred_by else None
    source_tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    control_session: Session = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())()
    try:
        control_session.add(
            CrossTenantReferralIndex(
                id=new_uuid_bytes(),
                referral_id=referral.id,
                source_tenant_id=tenant_id,
                target_tenant_id=referral.target_tenant_id,
                patient_id=referral.patient_id,
                patient_name=patient_name,
                patient_phone=patient.phone if patient else None,
                patient_dob=patient.date_of_birth if patient else None,
                patient_gender=patient.gender.value if patient and hasattr(patient.gender, "value") else (patient.gender if patient else None),
                patient_dui=patient.dui if patient else None,
                patient_nit=patient.nit if patient else None,
                patient_email=patient.email if patient else None,
                patient_address=patient.address if patient else None,
                patient_emergency_contact_name=patient.emergency_contact_name if patient else None,
                patient_emergency_contact_phone=patient.emergency_contact_phone if patient else None,
                patient_emergency_contact_relationship=patient.emergency_contact_relationship if patient else None,
                patient_insurance_type=patient.insurance_type.value if patient and hasattr(patient.insurance_type, "value") else (patient.insurance_type if patient else None),
                patient_insurance_number=patient.insurance_number if patient else None,
                referred_by_name=referral.referred_by_name,
                referred_by_specialty=referring_doctor.specialty if referring_doctor else None,
                source_tenant_name=source_tenant.name if source_tenant else tenant_id,
                target_doctor_id=referral.target_doctor_id,
                target_doctor_name=referral.target_doctor_name,
                destination_area=referral.destination_area,
                transfer_reason=referral.transfer_reason,
                status=referral.status.value if hasattr(referral.status, "value") else str(referral.status),
            )
        )
        control_session.commit()
    finally:
        control_session.close()


def generate_public_token(db: Session, referral_id: bytes, patient_id: bytes, clinical_record_id: bytes) -> PublicAccessToken:
    token = PublicAccessToken(
        id=new_uuid_bytes(),
        referral_id=referral_id,
        patient_id=patient_id,
        clinical_record_id=clinical_record_id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=72),
    )
    db.add(token)
    return token


def update_referral(db: Session, referral_id: bytes, tenant_id: str, data: ReferralUpdate, user_id: bytes) -> Referral:
    referral = db.query(Referral).filter(Referral.id == referral_id, Referral.tenant_id == tenant_id).first()
    if not referral:
        raise not_found("Referral not found.")
    if data.status is not None and data.status != referral.status:
        if data.status not in REFERRAL_ALLOWED_TRANSITIONS[referral.status]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No se puede pasar la referencia de '{referral.status.value}' a '{data.status.value}'",
            )
    old = model_to_dict(referral)
    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(referral, field, value)
    audit(db, user_id=user_id, tenant_id=tenant_id, action="UPDATE", table_name="referrals", record_id=referral.id, old_values=old, new_values=model_to_dict(referral))
    commit_or_409(db)
    db.refresh(referral)
    return referral


def accept_internal_transfer(db: Session, referral_id: bytes, tenant_id: str, user_id: bytes) -> Referral:
    referral = db.query(Referral).filter(Referral.id == referral_id, Referral.tenant_id == tenant_id).first()
    if not referral:
        raise not_found("Referral not found.")
    if referral.referral_type != ReferralType.internal_transfer:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La referencia no es un traslado interno.")
    old_referral = model_to_dict(referral)
    admission = (
        db.query(PatientAdmission)
        .filter(PatientAdmission.patient_id == referral.patient_id, PatientAdmission.tenant_id == tenant_id, PatientAdmission.status == AdmissionStatus.active)
        .first()
    )
    if admission:
        old_admission = model_to_dict(admission)
        admission.service = referral.destination_area
        audit(db, user_id=user_id, tenant_id=tenant_id, action="UPDATE", table_name="patient_admissions", record_id=admission.id, old_values=old_admission, new_values=model_to_dict(admission))
    referral.status = ReferralStatus.accepted
    audit(db, user_id=user_id, tenant_id=tenant_id, action="UPDATE", table_name="referrals", record_id=referral.id, old_values=old_referral, new_values=model_to_dict(referral))
    commit_or_409(db)
    db.refresh(referral)
    return referral
