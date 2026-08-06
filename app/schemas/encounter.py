from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.clinical import NoteType
from app.models.encounter import ClinicalOrderStatus, EncounterStatus
from app.schemas.common import ORMModel, TimestampMixin, patient_age_years


class EncounterStartRequest(ORMModel):
    patient_id: UUID | None = None
    appointment_id: UUID | None = None
    chief_complaint: str | None = Field(default=None, min_length=3)

    @model_validator(mode="after")
    def require_patient_or_appointment(self):
        if self.patient_id is None and self.appointment_id is None:
            raise ValueError("patient_id or appointment_id is required")
        return self


class EncounterCloseRequest(ORMModel):
    version: int = Field(ge=1)


class EncounterPatientSummary(ORMModel):
    id: UUID
    full_name: str
    age: int | None = None
    document: str | None = None


class EncounterDoctorSummary(ORMModel):
    id: UUID
    full_name: str


class EncounterSectionSummary(ORMModel):
    note_count: int = 0
    closed_note_count: int = 0
    diagnosis_count: int = 0
    prescription_count: int = 0
    vital_sign_count: int = 0
    order_count: int = 0


class EncounterRead(TimestampMixin):
    id: UUID
    appointment_id: UUID | None = None
    patient_id: UUID
    tenant_id: str
    doctor_id: UUID
    status: EncounterStatus
    chief_complaint: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    closed_at: datetime | None = None
    version: int
    patient: EncounterPatientSummary
    doctor: EncounterDoctorSummary
    summary: EncounterSectionSummary


class EncounterClinicalNoteCreate(ORMModel):
    encounter_id: UUID
    note_type: NoteType = NoteType.progress
    content: str = Field(min_length=1)


class EncounterClinicalNoteUpdate(ORMModel):
    content: str = Field(min_length=1)
    version: int = Field(ge=1)


class EncounterClinicalNoteClose(ORMModel):
    version: int = Field(ge=1)


class EncounterClinicalNoteRead(TimestampMixin):
    id: UUID
    encounter_id: UUID | None = None
    patient_id: UUID
    tenant_id: str
    note_type: NoteType
    content: str
    authored_by: UUID | None = None
    authored_by_name: str | None = None
    updated_by: UUID | None = None
    is_closed: bool
    closed_at: datetime | None = None
    version: int


DiagnosisKind = Literal["presumptive", "definitive", "ruled_out"]
DiagnosisClassification = Literal["primary", "secondary", "background"]
DiagnosisStatusLiteral = Literal["active", "resolved", "chronic", "recurrent"]
DiagnosisSeverityLiteral = Literal["mild", "moderate", "severe"]


class EncounterDiagnosisCreate(ORMModel):
    encounter_id: UUID
    clinical_record_id: UUID | None = None
    code: str = Field(min_length=3, max_length=10)
    description: str = Field(min_length=1, max_length=4000)
    type: DiagnosisKind
    classification: DiagnosisClassification
    status: DiagnosisStatusLiteral = "active"
    severity: DiagnosisSeverityLiteral | None = None
    is_first_time: bool = False
    notes: str | None = None


class EncounterDiagnosisUpdate(ORMModel):
    type: DiagnosisKind | None = None
    classification: DiagnosisClassification | None = None
    status: DiagnosisStatusLiteral | None = None
    severity: DiagnosisSeverityLiteral | None = None
    notes: str | None = None


class EncounterDiagnosisRead(TimestampMixin):
    id: UUID
    encounter_id: UUID | None = None
    code: str
    description: str
    type: DiagnosisKind
    classification: DiagnosisClassification
    status: DiagnosisStatusLiteral
    severity: DiagnosisSeverityLiteral | None = None
    is_first_time: bool
    notes: str | None = None
    version: int


class EncounterOrderCreate(ORMModel):
    encounter_id: UUID
    order_type: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1)
    scheduled_for: datetime | None = None
    notes: str | None = None


class EncounterOrderRead(TimestampMixin):
    id: UUID
    encounter_id: UUID
    patient_id: UUID
    tenant_id: str
    ordered_by: UUID
    order_type: str
    description: str
    status: ClinicalOrderStatus
    scheduled_for: datetime | None = None
    notes: str | None = None
    version: int
