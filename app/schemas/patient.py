from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.patient import (
    Alcohol,
    DeliveryRoute,
    Gender,
    ImmunizationStatus,
    InsuranceType,
    PatientConsentType,
    RhFactor,
    Severity,
    Smoking,
)
from app.schemas.common import (
    ClinicalAlert,
    ORMModel,
    SoftDeleteMixin,
    StrippedStringMixin,
    TimestampMixin,
    calculate_bmi,
    patient_age_years,
)


SOCIAL_INSURANCE_TYPES = {
    InsuranceType.ss_pensionado,
    InsuranceType.ss_cotizante,
    InsuranceType.ss_beneficiario,
}


class PatientBase(StrippedStringMixin, ORMModel):
    tenant_id: str = Field(min_length=1, max_length=50)
    medical_record_number: str = Field(min_length=1, max_length=50)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: date
    gender: Gender
    dui: str | None = Field(default=None, min_length=10, max_length=10, pattern=r"^\d{8}-\d$")
    nit: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=30)
    emergency_contact_relationship: str | None = Field(default=None, max_length=100)
    insurance_type: InsuranceType
    insurance_number: str | None = Field(default=None, max_length=50)
    attention_number: str | None = Field(default=None, max_length=50)
    last_employer: str | None = Field(default=None, max_length=255)
    work_phone: str | None = Field(default=None, max_length=30)
    last_occupation: str | None = Field(default=None, max_length=200)
    last_contribution_period: str | None = Field(default=None, max_length=50)
    last_work_date: date | None = None

    @model_validator(mode="after")
    def validate_business_rules(self):
        age = patient_age_years(self.date_of_birth)
        if age >= 18 and not self.dui:
            raise ValueError("el dui es obligatorio para pacientes adultos.")
        if self.insurance_type in SOCIAL_INSURANCE_TYPES and not self.insurance_number:
            raise ValueError("insurance_number es obligatorio para pacientes con seguro social.")
        if age >= 65:
            missing = [
                name
                for name in ("emergency_contact_name", "emergency_contact_phone", "emergency_contact_relationship")
                if not getattr(self, name)
            ]
            if missing:
                raise ValueError("nombre, telefono y parentesco del contacto de emergencia son obligatorios para pacientes de 65 anos o mas.")
        return self


class PatientCreate(PatientBase):
    pass


class PatientUpdate(StrippedStringMixin, ORMModel):
    medical_record_number: str | None = Field(default=None, min_length=1, max_length=50)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    date_of_birth: date | None = None
    gender: Gender | None = None
    dui: str | None = Field(default=None, min_length=10, max_length=10, pattern=r"^\d{8}-\d$")
    nit: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=30)
    emergency_contact_relationship: str | None = Field(default=None, max_length=100)
    insurance_type: InsuranceType | None = None
    insurance_number: str | None = Field(default=None, max_length=50)
    attention_number: str | None = Field(default=None, max_length=50)
    last_employer: str | None = Field(default=None, max_length=255)
    work_phone: str | None = Field(default=None, max_length=30)
    last_occupation: str | None = Field(default=None, max_length=200)
    last_contribution_period: str | None = Field(default=None, max_length=50)
    last_work_date: date | None = None

    @model_validator(mode="after")
    def validate_conditional_update(self):
        if self.insurance_type in SOCIAL_INSURANCE_TYPES and not self.insurance_number:
            raise ValueError("insurance_number es obligatorio al cambiar a un tipo de seguro social.")
        return self


class PatientRead(PatientBase, TimestampMixin, SoftDeleteMixin):
    id: UUID
    is_referred: bool = False


class PatientAllergyBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    allergen: str = Field(min_length=1, max_length=255)
    reaction: str | None = Field(default=None, max_length=255)
    severity: Severity
    notes: str | None = None
    is_active: bool = True


class PatientAllergyCreate(PatientAllergyBase):
    pass


class PatientAllergyUpdate(StrippedStringMixin, ORMModel):
    allergen: str | None = Field(default=None, min_length=1, max_length=255)
    reaction: str | None = Field(default=None, max_length=255)
    severity: Severity | None = None
    notes: str | None = None
    is_active: bool | None = None


class PatientAllergyRead(PatientAllergyBase):
    id: UUID
    created_at: datetime


class PatientMedicationBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    medication_name: str = Field(min_length=1, max_length=255)
    dose: str | None = Field(default=None, max_length=100)
    frequency: str | None = Field(default=None, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool = True
    prescribed_by: UUID | None = None
    prescribed_by_name: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class PatientMedicationCreate(PatientMedicationBase):
    pass


class PatientMedicationUpdate(StrippedStringMixin, ORMModel):
    medication_name: str | None = Field(default=None, min_length=1, max_length=255)
    dose: str | None = Field(default=None, max_length=100)
    frequency: str | None = Field(default=None, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None
    notes: str | None = None


class PatientMedicationRead(PatientMedicationBase):
    id: UUID
    created_at: datetime


class PatientPhysiologicalHxBase(ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    blood_type: str | None = Field(default=None, max_length=5)
    rh_factor: RhFactor | None = None
    smoking: Smoking = Smoking.never
    alcohol: Alcohol = Alcohol.never
    drugs: str | None = None
    notes: str | None = None


class PatientPhysiologicalHxCreate(PatientPhysiologicalHxBase):
    pass


class PatientPhysiologicalHxRead(PatientPhysiologicalHxBase, TimestampMixin):
    id: UUID


class PatientChronicDiseaseBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    disease_name: str = Field(min_length=1, max_length=255)
    cie10_code: str | None = Field(default=None, max_length=10)
    diagnosis_date: date | None = None
    is_active: bool = True
    notes: str | None = None


class PatientChronicDiseaseCreate(PatientChronicDiseaseBase):
    pass


class PatientChronicDiseaseRead(PatientChronicDiseaseBase):
    id: UUID
    created_at: datetime


class PatientSurgeryBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    surgery_name: str = Field(min_length=1, max_length=255)
    surgery_date: date | None = None
    hospital: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class PatientSurgeryCreate(PatientSurgeryBase):
    pass


class PatientSurgeryRead(PatientSurgeryBase):
    id: UUID
    created_at: datetime


class PatientHospitalizationHxBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    admission_date: date
    discharge_date: date | None = None
    reason: str | None = None
    hospital: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class PatientHospitalizationHxCreate(PatientHospitalizationHxBase):
    pass


class PatientHospitalizationHxRead(PatientHospitalizationHxBase):
    id: UUID
    created_at: datetime


class PatientFamilyHxBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    relationship: str | None = Field(default=None, max_length=100)
    condition_name: str | None = Field(default=None, max_length=255)
    cie10_code: str | None = Field(default=None, max_length=10)
    notes: str | None = None


class PatientFamilyHxCreate(PatientFamilyHxBase):
    pass


class PatientFamilyHxRead(PatientFamilyHxBase):
    id: UUID
    created_at: datetime


class PatientGynecologicalHxBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    menarche_age: int | None = Field(default=None, ge=6, le=18)
    last_menstrual_period: date | None = None
    pregnancies: int | None = Field(default=None, ge=0, le=30)
    deliveries: int | None = Field(default=None, ge=0, le=30)
    abortions: int | None = Field(default=None, ge=0, le=30)
    contraceptive_method: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class PatientGynecologicalHxCreate(PatientGynecologicalHxBase):
    pass


class PatientGynecologicalHxRead(PatientGynecologicalHxBase):
    id: UUID
    created_at: datetime


class PatientSocialHxBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    occupation: str | None = Field(default=None, max_length=255)
    living_conditions: str | None = None
    housing_type: str | None = Field(default=None, max_length=100)
    has_water: bool | None = None
    has_sewer: bool | None = None
    has_electricity: bool | None = None
    pets: str | None = None
    notes: str | None = None


class PatientSocialHxCreate(PatientSocialHxBase):
    pass


class PatientSocialHxRead(PatientSocialHxBase):
    id: UUID
    created_at: datetime


class PatientPerinatalHxBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    gestational_weeks: int | None = Field(default=None, ge=20, le=45)
    prenatal_controls: int | None = Field(default=None, ge=0, le=30)
    delivery_route: DeliveryRoute | None = None
    birth_weight: Decimal | None = Field(default=None, gt=0, le=9999)
    birth_length: Decimal | None = Field(default=None, gt=0, le=80)
    head_circumference: Decimal | None = Field(default=None, gt=0, le=70)
    apgar_1min: int | None = Field(default=None, ge=0, le=10)
    apgar_5min: int | None = Field(default=None, ge=0, le=10)
    apgar_10min: int | None = Field(default=None, ge=0, le=10)
    ballard_weeks: int | None = Field(default=None, ge=20, le=45)
    silverman_retractions: int | None = Field(default=None, ge=0, le=2)
    silverman_cyanosis: int | None = Field(default=None, ge=0, le=2)
    silverman_grunting: int | None = Field(default=None, ge=0, le=2)
    silverman_breathing: int | None = Field(default=None, ge=0, le=2)
    silverman_auscultation: int | None = Field(default=None, ge=0, le=2)
    silverman_total: int | None = Field(default=None, ge=0, le=10)
    nicu_admission: bool | None = None
    notes: str | None = None
    alert: ClinicalAlert = Field(default_factory=ClinicalAlert)

    @model_validator(mode="after")
    def calculate_silverman(self):
        parts = [
            self.silverman_retractions,
            self.silverman_cyanosis,
            self.silverman_grunting,
            self.silverman_breathing,
            self.silverman_auscultation,
        ]
        if all(part is not None for part in parts):
            self.silverman_total = sum(parts)  # type: ignore[arg-type]
        if self.silverman_total is not None and self.silverman_total >= 5:
            self.alert.alert_triggered = True
            self.alert.alert_type.append("silverman_high")
            self.alert.alert_messages.append("Silverman-Anderson score suggests respiratory distress.")
        return self


class PatientPerinatalHxCreate(PatientPerinatalHxBase):
    pass


class PatientPerinatalHxRead(PatientPerinatalHxBase):
    id: UUID
    created_at: datetime


class PatientDevelopmentHxBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    walking_age_months: Decimal | None = Field(default=None, ge=0, le=120)
    first_words_age_months: Decimal | None = Field(default=None, ge=0, le=120)
    toilet_training_age_months: Decimal | None = Field(default=None, ge=0, le=120)
    notes: str | None = None


class PatientDevelopmentHxCreate(PatientDevelopmentHxBase):
    pass


class PatientDevelopmentHxRead(PatientDevelopmentHxBase):
    id: UUID
    created_at: datetime


class PatientConsentBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    consent_type: PatientConsentType
    consent_text: str = Field(min_length=1)
    signed_by: UUID | None = None
    pdf_url: str | None = Field(default=None, max_length=500)
    revoked_at: datetime | None = None


class PatientConsentCreate(PatientConsentBase):
    pass


class PatientConsentRead(PatientConsentBase):
    id: UUID
    signed_at: datetime
    created_at: datetime


class PatientImmunizationBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    vaccine_name: str = Field(min_length=1, max_length=255)
    dose_number: str | None = Field(default=None, max_length=50)
    lot_number: str | None = Field(default=None, max_length=100)
    applied_at: date | None = None
    next_due_at: date | None = None
    applied_by: UUID | None = None
    status: ImmunizationStatus = ImmunizationStatus.applied
    notes: str | None = None


class PatientImmunizationCreate(PatientImmunizationBase):
    pass


class PatientImmunizationRead(PatientImmunizationBase):
    id: UUID
    created_at: datetime


class PatientGrowthMeasurementBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    clinical_record_id: UUID | None = None
    measured_at: datetime | None = None
    weight: Decimal | None = Field(default=None, gt=0, le=500)
    height: Decimal | None = Field(default=None, gt=0, le=250)
    head_circumference: Decimal | None = Field(default=None, gt=0, le=80)
    bmi: Decimal | None = Field(default=None, ge=5, le=100)
    weight_percentile: Decimal | None = Field(default=None, ge=0, le=100)
    height_percentile: Decimal | None = Field(default=None, ge=0, le=100)
    bmi_percentile: Decimal | None = Field(default=None, ge=0, le=100)
    recorded_by: UUID | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def calculate_bmi_field(self):
        if self.bmi is None:
            self.bmi = calculate_bmi(self.weight, self.height)
        return self


class PatientGrowthMeasurementCreate(PatientGrowthMeasurementBase):
    pass


class PatientGrowthMeasurementRead(PatientGrowthMeasurementBase):
    id: UUID
    created_at: datetime


class PatientDevelopmentRecordBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    milestone_id: UUID
    achieved_at: date | None = None
    delay_alert: bool = False
    recorded_by: UUID | None = None
    notes: str | None = None


class PatientDevelopmentRecordCreate(PatientDevelopmentRecordBase):
    pass


class PatientDevelopmentRecordRead(PatientDevelopmentRecordBase):
    id: UUID
    created_at: datetime
