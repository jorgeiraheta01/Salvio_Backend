from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from app.models.appointment import AdmissionStatus, AppointmentStatus, TriagePriority
from app.schemas.common import ClinicalAlert, ORMModel, SoftDeleteMixin, StrippedStringMixin, TimestampMixin, vital_alerts


APPOINTMENT_STATUS_ORDER = {
    AppointmentStatus.scheduled: 0,
    AppointmentStatus.confirmed: 1,
    AppointmentStatus.checked_in: 2,
    AppointmentStatus.in_consultation: 3,
    AppointmentStatus.completed: 4,
    AppointmentStatus.cancelled: 4,
    AppointmentStatus.no_show: 4,
    AppointmentStatus.rescheduled: 4,
}


class AppointmentBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    doctor_id: UUID
    scheduled_at: datetime
    appointment_type: str | None = Field(default=None, max_length=100)
    status: AppointmentStatus = AppointmentStatus.scheduled
    notes: str | None = None


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(StrippedStringMixin, ORMModel):
    scheduled_at: datetime | None = None
    appointment_type: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class AppointmentStatusUpdate(ORMModel):
    status: AppointmentStatus
    current_status: AppointmentStatus | None = None
    reason: str | None = Field(default=None, min_length=3)

    @model_validator(mode="after")
    def validate_forward_status(self):
        if self.current_status is not None:
            if APPOINTMENT_STATUS_ORDER[self.status] < APPOINTMENT_STATUS_ORDER[self.current_status]:
                raise ValueError("el estado de la cita no puede retroceder.")
        if self.status in {AppointmentStatus.cancelled, AppointmentStatus.no_show, AppointmentStatus.rescheduled} and not self.reason:
            raise ValueError("el motivo es obligatorio para citas canceladas, no presentadas o reprogramadas.")
        return self


class AppointmentRead(AppointmentBase, TimestampMixin, SoftDeleteMixin):
    id: UUID


class AppointmentRescheduleRequest(ORMModel):
    new_scheduled_at: datetime
    new_doctor_id: UUID | None = None
    reason: str = Field(min_length=3)


class PatientAdmissionBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    admission_datetime: datetime
    discharge_datetime: datetime | None = None
    service: str | None = Field(default=None, max_length=100)
    bed_number: str | None = Field(default=None, max_length=20)
    admitting_doctor: UUID | None = None
    admitting_doctor_name: str | None = Field(default=None, max_length=255)
    diagnosis_on_admission: str | None = None
    discharge_diagnosis_cie10: str | None = Field(default=None, max_length=10)
    status: AdmissionStatus = AdmissionStatus.active


class PatientAdmissionCreate(PatientAdmissionBase):
    pass


class PatientAdmissionUpdate(StrippedStringMixin, ORMModel):
    discharge_datetime: datetime | None = None
    service: str | None = Field(default=None, max_length=100)
    bed_number: str | None = Field(default=None, max_length=20)
    discharge_diagnosis_cie10: str | None = Field(default=None, max_length=10)
    status: AdmissionStatus | None = None


class PatientAdmissionRead(PatientAdmissionBase, TimestampMixin):
    id: UUID


class TriageRecordBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    appointment_id: UUID | None = None
    admission_id: UUID | None = None
    received_at: datetime
    triage_at: datetime | None = None
    nursing_prep_at: datetime | None = None
    priority: TriagePriority
    area: str | None = Field(default=None, max_length=100)
    systolic_bp: int | None = Field(default=None, ge=40, le=300)
    diastolic_bp: int | None = Field(default=None, ge=20, le=200)
    heart_rate: int | None = Field(default=None, ge=20, le=250)
    resp_rate: int | None = Field(default=None, ge=4, le=80)
    temperature: float | None = Field(default=None, ge=25, le=45)
    spo2: int | None = Field(default=None, ge=0, le=100)
    glasgow_total: int | None = Field(default=None, ge=3, le=15)
    chief_complaint: str | None = None
    created_by: UUID | None = None
    alert: ClinicalAlert = Field(default_factory=ClinicalAlert)

    @model_validator(mode="after")
    def calculate_alerts(self):
        self.alert = vital_alerts(
            glasgow_total=self.glasgow_total,
            bp_systolic=self.systolic_bp,
            bp_diastolic=self.diastolic_bp,
            spo2=self.spo2,
            temperature=self.temperature,
        )
        return self


class TriageRecordCreate(TriageRecordBase):
    pass


class TriageRecordRead(TriageRecordBase):
    id: UUID
    created_at: datetime
