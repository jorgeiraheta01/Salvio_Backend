from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.patient import Severity
from app.models.prescription import PrescriptionItemStatus, PrescriptionStatus
from app.schemas.common import ClinicalAlert, ORMModel, StrippedStringMixin


class AllergyAlert(StrippedStringMixin, ORMModel):
    medication: str = Field(min_length=1, max_length=255)
    allergen: str = Field(min_length=1, max_length=255)
    severity: Severity
    reaction: str | None = Field(default=None, max_length=255)


class PrescriptionItemBase(StrippedStringMixin, ORMModel):
    prescription_id: UUID | None = None
    tenant_id: str | None = Field(default=None, max_length=50)
    medication_name: str = Field(min_length=1, max_length=255)
    medication_code: str | None = Field(default=None, max_length=50)
    concentration: str | None = Field(default=None, max_length=100)
    pharmaceutical_form: str | None = Field(default=None, max_length=100)
    dose: str | None = Field(default=None, max_length=100)
    frequency: str | None = Field(default=None, max_length=100)
    duration: str | None = Field(default=None, max_length=100)
    route: str | None = Field(default=None, max_length=100)
    quantity: Decimal | None = Field(default=None, gt=0)
    refills: int = Field(default=0, ge=0, le=12)
    start_date: date | None = None
    end_date: date | None = None
    indication: str | None = Field(default=None, max_length=255)
    instructions: str | None = None
    status: PrescriptionItemStatus = PrescriptionItemStatus.active
    notes: str | None = None


class PrescriptionItemCreate(PrescriptionItemBase):
    name: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="before")
    @classmethod
    def support_contract_name(cls, data):
        if isinstance(data, dict) and "name" in data and "medication_name" not in data:
            data["medication_name"] = data["name"]
        return data


class PrescriptionItemUpdate(StrippedStringMixin, ORMModel):
    medication_name: str | None = Field(default=None, min_length=1, max_length=255)
    dose: str | None = Field(default=None, max_length=100)
    frequency: str | None = Field(default=None, max_length=100)
    duration: str | None = Field(default=None, max_length=100)
    route: str | None = Field(default=None, max_length=100)
    quantity: Decimal | None = Field(default=None, gt=0)
    refills: int | None = Field(default=None, ge=0, le=12)
    status: PrescriptionItemStatus | None = None
    notes: str | None = None


class PrescriptionItemRead(PrescriptionItemBase):
    id: UUID
    prescription_id: UUID
    tenant_id: str
    created_at: datetime
    updated_at: datetime | None = None


class PrescriptionBase(StrippedStringMixin, ORMModel):
    patient_id: UUID | None = None
    tenant_id: str | None = Field(default=None, max_length=50)
    encounter_id: UUID | None = None
    clinical_record_id: UUID | None = None
    prescribed_by: UUID | None = None
    prescribed_by_name: str | None = Field(default=None, min_length=1, max_length=255)
    prescribed_at: datetime | None = None
    pdf_url: str | None = Field(default=None, max_length=500)
    status: PrescriptionStatus = PrescriptionStatus.active


class PrescriptionCreate(PrescriptionBase):
    medications: list[PrescriptionItemCreate] = Field(min_length=1)
    known_allergy_alerts: list[AllergyAlert] = Field(default_factory=list)

    @model_validator(mode="after")
    def flag_known_allergies(self):
        if self.patient_id is None and self.encounter_id is None:
            raise ValueError("patient_id or encounter_id is required.")
        if self.known_allergy_alerts:
            for item in self.medications:
                item.status = PrescriptionItemStatus.suspended
        return self


class PrescriptionUpdate(StrippedStringMixin, ORMModel):
    pdf_url: str | None = Field(default=None, max_length=500)
    status: PrescriptionStatus | None = None


class PrescriptionRead(PrescriptionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None = None
    version: int = 1
    items: list[PrescriptionItemRead] = Field(default_factory=list)


class PrescriptionCreateResponse(ORMModel):
    id: UUID | None = None
    allergy_alerts: list[AllergyAlert] = Field(default_factory=list)
    status: str = "created"
    pdf_url: str | None = None
    alert: ClinicalAlert = Field(default_factory=ClinicalAlert)

    @model_validator(mode="after")
    def set_allergy_alert(self):
        if self.allergy_alerts:
            self.alert.alert_triggered = True
            self.alert.alert_type.append("allergy_match")
            self.alert.alert_messages.append("Prescription contains at least one medication matching active allergies.")
        return self


class AllergyOverrideRequest(StrippedStringMixin, ORMModel):
    medication: str = Field(min_length=1, max_length=255)
    override_reason: str = Field(min_length=10)
    overridden_by: UUID


class AllergyOverrideResponse(ORMModel):
    id: UUID
    override_recorded: bool = True
