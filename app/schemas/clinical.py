from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from app.models.clinical import ClinicalRecordStatus, DiagnosisType, NoteType, ScaleName
from app.schemas.common import ClinicalAlert, ORMModel, SoftDeleteMixin, StrippedStringMixin, TimestampMixin, calculate_bmi, vital_alerts


class ClinicalRecordBase(StrippedStringMixin, ORMModel):
    appointment_id: UUID | None = None
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    doctor_id: UUID
    doctor_name: str = Field(min_length=1, max_length=255)
    status: ClinicalRecordStatus = ClinicalRecordStatus.draft
    soap_subjective: str | None = None
    soap_objective: str | None = None
    soap_assessment: str | None = None
    soap_plan: str | None = None
    informant: str | None = Field(default=None, max_length=255)
    informant_relationship: str | None = Field(default=None, max_length=100)
    visit_number: int | None = Field(default=None, ge=1, le=32767)
    printed_at: datetime | None = None
    signed_at: datetime | None = None
    digital_signature: str | None = None


class ClinicalRecordCreate(ClinicalRecordBase):
    status: ClinicalRecordStatus = ClinicalRecordStatus.draft


class ClinicalRecordUpdate(StrippedStringMixin, ORMModel):
    soap_subjective: str | None = None
    soap_objective: str | None = None
    soap_assessment: str | None = None
    soap_plan: str | None = None
    informant: str | None = Field(default=None, max_length=255)
    informant_relationship: str | None = Field(default=None, max_length=100)
    visit_number: int | None = Field(default=None, ge=1, le=32767)


class ClinicalRecordSignRequest(ORMModel):
    digital_signature: str = Field(min_length=16)
    signed_by: UUID
    has_primary_diagnosis: bool = False

    @model_validator(mode="after")
    def require_primary_diagnosis(self):
        if not self.has_primary_diagnosis:
            raise ValueError("un expediente clinico firmado requiere un diagnostico primario.")
        return self


class ClinicalRecordRead(ClinicalRecordBase, TimestampMixin, SoftDeleteMixin):
    id: UUID


class VitalSignBase(ORMModel):
    patient_id: UUID | None = None
    tenant_id: str | None = Field(default=None, max_length=50)
    encounter_id: UUID | None = None
    clinical_record_id: UUID | None = None
    recorded_at: datetime | None = None
    bp_systolic: int | None = Field(default=None, ge=40, le=300, description="mmHg")
    bp_diastolic: int | None = Field(default=None, ge=20, le=200, description="mmHg")
    heart_rate: int | None = Field(default=None, ge=20, le=250)
    resp_rate: int | None = Field(default=None, ge=4, le=80)
    temperature: Decimal | None = Field(default=None, ge=25, le=45)
    spo2: int | None = Field(default=None, ge=0, le=100)
    fio2: int | None = Field(default=None, ge=21, le=100)
    glucometria: int | None = Field(default=None, ge=20, le=800)
    weight: Decimal | None = Field(default=None, gt=0, le=500)
    height: Decimal | None = Field(default=None, gt=0, le=250)
    bmi_calculated: Decimal | None = Field(default=None, ge=5, le=100)
    pain_scale_eva: int | None = Field(default=None, ge=0, le=10)
    glasgow_ocular: int | None = Field(default=None, ge=1, le=4)
    glasgow_verbal: int | None = Field(default=None, ge=1, le=5)
    glasgow_motor: int | None = Field(default=None, ge=1, le=6)
    glasgow_total: int | None = Field(default=None, ge=3, le=15)
    perimetro_cefalico: Decimal | None = Field(default=None, gt=0, le=80)
    flacc: int | None = Field(default=None, ge=0, le=10)
    recorded_by: UUID | None = None
    alert: ClinicalAlert = Field(default_factory=ClinicalAlert)

    @model_validator(mode="after")
    def calculate_derived_fields(self):
        if self.patient_id is None and self.encounter_id is None and self.clinical_record_id is None:
            raise ValueError("se requiere patient_id, encounter_id o clinical_record_id.")
        glasgow_parts = [self.glasgow_ocular, self.glasgow_verbal, self.glasgow_motor]
        if all(part is not None for part in glasgow_parts):
            self.glasgow_total = sum(glasgow_parts)  # type: ignore[arg-type]
        if self.bmi_calculated is None:
            self.bmi_calculated = calculate_bmi(self.weight, self.height)
        self.alert = vital_alerts(
            glasgow_total=self.glasgow_total,
            bp_systolic=self.bp_systolic,
            bp_diastolic=self.bp_diastolic,
            spo2=self.spo2,
            temperature=self.temperature,
            glucometria=self.glucometria,
        )
        return self


class VitalSignCreate(VitalSignBase):
    pass


class VitalSignUpdate(ORMModel):
    bp_systolic: int | None = Field(default=None, ge=40, le=300)
    bp_diastolic: int | None = Field(default=None, ge=20, le=200)
    heart_rate: int | None = Field(default=None, ge=20, le=250)
    resp_rate: int | None = Field(default=None, ge=4, le=80)
    temperature: Decimal | None = Field(default=None, ge=25, le=45)
    spo2: int | None = Field(default=None, ge=0, le=100)
    fio2: int | None = Field(default=None, ge=21, le=100)
    glucometria: int | None = Field(default=None, ge=20, le=800)
    weight: Decimal | None = Field(default=None, gt=0, le=500)
    height: Decimal | None = Field(default=None, gt=0, le=250)
    pain_scale_eva: int | None = Field(default=None, ge=0, le=10)
    glasgow_ocular: int | None = Field(default=None, ge=1, le=4)
    glasgow_verbal: int | None = Field(default=None, ge=1, le=5)
    glasgow_motor: int | None = Field(default=None, ge=1, le=6)
    perimetro_cefalico: Decimal | None = Field(default=None, gt=0, le=80)
    flacc: int | None = Field(default=None, ge=0, le=10)


class VitalSignRead(VitalSignBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None = None
    version: int = 1


class PhysicalExamFindingBase(StrippedStringMixin, ORMModel):
    clinical_record_id: UUID
    tenant_id: str = Field(max_length=50)
    system_name: str = Field(min_length=1, max_length=100)
    is_normal: bool | None = None
    findings: str | None = None


class PhysicalExamFindingCreate(PhysicalExamFindingBase):
    pass


class PhysicalExamFindingRead(PhysicalExamFindingBase):
    id: UUID
    created_at: datetime


class ReviewOfSystemBase(StrippedStringMixin, ORMModel):
    clinical_record_id: UUID
    tenant_id: str = Field(max_length=50)
    system_name: str = Field(min_length=1, max_length=100)
    is_positive: bool | None = None
    comments: str | None = None


class ReviewOfSystemCreate(ReviewOfSystemBase):
    pass


class ReviewOfSystemRead(ReviewOfSystemBase):
    id: UUID
    created_at: datetime


class ClinicalProblemBase(StrippedStringMixin, ORMModel):
    clinical_record_id: UUID
    tenant_id: str = Field(max_length=50)
    problem_name: str = Field(min_length=1, max_length=255)
    is_active: bool = True
    notes: str | None = None


class ClinicalProblemCreate(ClinicalProblemBase):
    pass


class ClinicalProblemRead(ClinicalProblemBase):
    id: UUID
    created_at: datetime


class RecordDiagnosisBase(StrippedStringMixin, ORMModel):
    clinical_record_id: UUID
    tenant_id: str = Field(max_length=50)
    clinical_problem_id: UUID | None = None
    cie10_code: str = Field(min_length=3, max_length=10)
    cie10_description: str = Field(min_length=1, max_length=255)
    diagnosis_type: DiagnosisType
    is_first_time: bool
    is_primary_diagnosis: bool
    is_background: bool
    is_outpatient: bool
    notes: str | None = None


class RecordDiagnosisCreate(RecordDiagnosisBase):
    pass


class RecordDiagnosisUpdate(StrippedStringMixin, ORMModel):
    diagnosis_type: DiagnosisType | None = None
    is_first_time: bool | None = None
    is_primary_diagnosis: bool | None = None
    is_background: bool | None = None
    is_outpatient: bool | None = None
    notes: str | None = None


class RecordDiagnosisRead(RecordDiagnosisBase):
    id: UUID
    created_at: datetime


class RecordPlanBase(StrippedStringMixin, ORMModel):
    clinical_record_id: UUID
    tenant_id: str = Field(max_length=50)
    plan_type: str | None = Field(default=None, max_length=100)
    description: str | None = None
    due_date: date | None = None
    completed_at: datetime | None = None


class RecordPlanCreate(RecordPlanBase):
    pass


class RecordPlanRead(RecordPlanBase):
    id: UUID
    created_at: datetime


class ClinicalNoteBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    admission_id: UUID | None = None
    clinical_record_id: UUID | None = None
    note_type: NoteType
    content: str = Field(min_length=1)
    authored_by: UUID | None = None
    authored_by_name: str | None = Field(default=None, max_length=255)


class ClinicalNoteCreate(ClinicalNoteBase):
    pass


class CorrectionNoteCreate(StrippedStringMixin, ORMModel):
    clinical_record_id: UUID
    note_text: str = Field(min_length=1)
    created_by: UUID


class ClinicalNoteRead(ClinicalNoteBase):
    id: UUID
    created_at: datetime


class ClinicalScaleResultBase(ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    clinical_record_id: UUID | None = None
    scale_name: ScaleName
    total_score: int | None = Field(default=None, ge=0, le=100)
    risk_level: str | None = Field(default=None, max_length=50)
    details: dict[str, Any] | None = None
    performed_by: UUID | None = None
    performed_at: datetime | None = None
    alert: ClinicalAlert = Field(default_factory=ClinicalAlert)

    @model_validator(mode="after")
    def calculate_scale_alert(self):
        if self.scale_name == ScaleName.eva and self.total_score is not None and self.total_score >= 7:
            self.alert.alert_triggered = True
            self.alert.alert_type.append("pain_high")
            self.alert.alert_messages.append("EVA pain score is high.")
        if self.scale_name == ScaleName.flacc and self.total_score is not None and self.total_score >= 7:
            self.alert.alert_triggered = True
            self.alert.alert_type.append("pediatric_pain_high")
            self.alert.alert_messages.append("FLACC pain score is high.")
        if self.scale_name == ScaleName.braden and self.total_score is not None and self.total_score <= 12:
            self.alert.alert_triggered = True
            self.alert.alert_type.append("pressure_ulcer_risk")
            self.alert.alert_messages.append("Braden score indicates high risk.")
        return self


class ClinicalScaleResultCreate(ClinicalScaleResultBase):
    pass


class ClinicalScaleResultRead(ClinicalScaleResultBase):
    id: UUID
    created_at: datetime


class ClinicalProcedureBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    clinical_record_id: UUID | None = None
    consent_id: UUID | None = None
    procedure_name: str = Field(min_length=1, max_length=255)
    performed_by: UUID | None = None
    performed_by_name: str | None = Field(default=None, max_length=255)
    performed_at: datetime | None = None
    notes: str | None = None


class ClinicalProcedureCreate(ClinicalProcedureBase):
    pass


class ClinicalProcedureRead(ClinicalProcedureBase):
    id: UUID
    created_at: datetime


class ClinicalRecordDetail(ClinicalRecordRead):
    vital_signs: list[VitalSignRead] = Field(default_factory=list)
    diagnoses: list[RecordDiagnosisRead] = Field(default_factory=list)
    physical_exam_findings: list[PhysicalExamFindingRead] = Field(default_factory=list)
    review_of_systems: list[ReviewOfSystemRead] = Field(default_factory=list)
    plans: list[RecordPlanRead] = Field(default_factory=list)
    notes: list[ClinicalNoteRead] = Field(default_factory=list)
    scales: list[ClinicalScaleResultRead] = Field(default_factory=list)
