from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.referral import InterconsultStatus, ReferralStatus, ReferralType
from app.schemas.common import ORMModel, StrippedStringMixin


class InterconsultBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    clinical_record_id: UUID | None = None
    requesting_doctor: UUID
    requesting_doctor_name: str = Field(min_length=1, max_length=255)
    consulting_specialty: str = Field(min_length=1, max_length=100)
    reason: str | None = None
    requested_at: datetime | None = None
    response: str | None = None
    responded_at: datetime | None = None
    status: InterconsultStatus = InterconsultStatus.pending


class InterconsultCreate(InterconsultBase):
    pass


class InterconsultRespond(StrippedStringMixin, ORMModel):
    response: str = Field(min_length=1)
    responded_at: datetime | None = None
    status: InterconsultStatus = InterconsultStatus.completed


class InterconsultRead(InterconsultBase):
    id: UUID
    created_at: datetime


class ReferralBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    clinical_record_id: UUID | None = None
    referral_type: ReferralType
    source_service: str | None = Field(default=None, max_length=100)
    destination_area: str | None = Field(default=None, max_length=100)
    transfer_reason: str | None = None
    referred_by: UUID | None = None
    referred_by_name: str | None = Field(default=None, max_length=255)
    target_tenant_id: str | None = Field(default=None, max_length=50)
    target_doctor_id: UUID | None = None
    target_doctor_name: str | None = Field(default=None, max_length=255)
    status: ReferralStatus = ReferralStatus.pending

    @model_validator(mode="after")
    def validate_referral_type_fields(self):
        if self.referral_type == ReferralType.internal_transfer:
            if not self.source_service or not self.destination_area or not self.transfer_reason:
                raise ValueError("las referencias internal_transfer requieren source_service, destination_area y transfer_reason.")
        if self.referral_type == ReferralType.cross_tenant and not self.target_tenant_id:
            raise ValueError("las referencias cross_tenant requieren target_tenant_id.")
        return self


class ReferralCreate(ReferralBase):
    pass


class ReferralUpdate(StrippedStringMixin, ORMModel):
    source_service: str | None = Field(default=None, max_length=100)
    destination_area: str | None = Field(default=None, max_length=100)
    transfer_reason: str | None = None
    target_tenant_id: str | None = Field(default=None, max_length=50)
    status: ReferralStatus | None = None


class ReferralRead(ReferralBase):
    id: UUID
    created_at: datetime


class OutgoingReferralRead(ORMModel):
    """Vista compacta de una referencia ya enviada, para el lado que refirio
    (ver GET /referrals/by-patient/{patient_id}) -- de un vistazo, a quien y
    donde se remitio a este paciente, sin tener que ir a Operaciones."""

    id: UUID
    referral_type: ReferralType
    target_tenant_id: str | None = None
    target_tenant_name: str | None = None
    target_doctor_name: str | None = None
    destination_area: str | None = None
    transfer_reason: str | None = None
    status: ReferralStatus
    created_at: datetime


class PublicAccessTokenCreate(ORMModel):
    referral_id: UUID | None = None
    patient_id: UUID
    clinical_record_id: UUID
    token: str = Field(min_length=32, max_length=255)
    expires_at: datetime

    @model_validator(mode="after")
    def validate_max_72h(self):
        if self.expires_at > datetime.now(timezone.utc) + timedelta(hours=72):
            raise ValueError("los tokens de acceso publico no pueden expirar en mas de 72 horas.")
        return self


class PublicAccessTokenRead(PublicAccessTokenCreate):
    id: UUID
    created_at: datetime


class IncomingCrossTenantReferral(ORMModel):
    id: UUID
    referral_id: UUID
    source_tenant_id: str
    target_tenant_id: str
    patient_id: UUID
    patient_name: str
    patient_phone: str | None = None
    patient_dob: date | None = None
    patient_gender: str | None = None
    patient_dui: str | None = None
    referred_by_name: str | None = None
    referred_by_specialty: str | None = None
    source_tenant_name: str | None = None
    target_doctor_id: UUID | None = None
    target_doctor_name: str | None = None
    destination_area: str | None = None
    transfer_reason: str | None = None
    status: str
    imported_patient_id: UUID | None = None
    created_at: datetime


class CrossTenantReferralStatusUpdate(ORMModel):
    status: Literal["accepted", "completed", "rejected"]


class NetworkDoctor(ORMModel):
    id: UUID
    full_name: str
    specialty: str | None = None
    tenant_id: str
    tenant_name: str | None = None


class ImportedPatientRead(ORMModel):
    patient_id: UUID
    already_existed: bool


class CrossTenantEncounterNote(ORMModel):
    note_type: str
    content: str
    authored_by_name: str | None = None
    is_closed: bool
    created_at: datetime


class CrossTenantEncounterDiagnosis(ORMModel):
    code: str
    description: str
    classification: str
    severity: str | None = None


class CrossTenantEncounterSummary(ORMModel):
    id: UUID
    doctor_name: str | None = None
    chief_complaint: str | None = None
    status: str
    started_at: datetime
    closed_at: datetime | None = None
    notes: list[CrossTenantEncounterNote]
    diagnoses: list[CrossTenantEncounterDiagnosis]


class CrossTenantPatientSummary(ORMModel):
    id: UUID
    full_name: str
    date_of_birth: date
    gender: str
    dui: str | None = None


class CrossTenantHistoryRead(ORMModel):
    source_tenant_id: str
    source_tenant_name: str | None = None
    referral: IncomingCrossTenantReferral
    patient: CrossTenantPatientSummary
    encounters: list[CrossTenantEncounterSummary]
