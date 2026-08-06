from sqlalchemy import Column, String, Boolean, DateTime, Date, Enum as SQLEnum, ForeignKey, Text, SmallInteger, DECIMAL, Index, JSON, Integer
from sqlalchemy.dialects.mysql import BINARY, TINYINT
from sqlalchemy.sql import func
from app.database import Base
import enum

# =====================================================================
# ENUMS
# =====================================================================
class ClinicalRecordStatus(str, enum.Enum):
    draft = "draft"
    signed = "signed"

class DiagnosisType(str, enum.Enum):
    presumptive = "presumptive"
    definitive = "definitive"
    ruled_out = "ruled_out"

class DiagnosisStatus(str, enum.Enum):
    active = "active"
    resolved = "resolved"
    chronic = "chronic"
    recurrent = "recurrent"

class DiagnosisSeverity(str, enum.Enum):
    mild = "mild"
    moderate = "moderate"
    severe = "severe"

class NoteType(str, enum.Enum):
    progress = "progress"
    nursing = "nursing"
    discharge = "discharge"
    other = "other"

class ScaleName(str, enum.Enum):
    barthel = "barthel"
    braden = "braden"
    morse = "morse"
    asa = "asa"
    silverman = "silverman"
    flacc = "flacc"
    eva = "eva"

# =====================================================================
# 024 · CLINICAL RECORDS
# =====================================================================
class ClinicalRecord(Base):
    __tablename__ = "clinical_records"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    appointment_id = Column(BINARY(16), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True)
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    doctor_id = Column(BINARY(16), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    doctor_name = Column(String(255), nullable=False)
    status = Column(SQLEnum(ClinicalRecordStatus), nullable=False, default="draft")
    soap_subjective = Column(Text, nullable=True)
    soap_objective = Column(Text, nullable=True)
    soap_assessment = Column(Text, nullable=True)
    soap_plan = Column(Text, nullable=True)
    informant = Column(String(255), nullable=True)
    informant_relationship = Column(String(100), nullable=True)
    visit_number = Column(SmallInteger, nullable=True)
    printed_at = Column(DateTime, nullable=True)
    signed_at = Column(DateTime, nullable=True)
    digital_signature = Column(Text, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_cr_patient", "patient_id"),
        Index("idx_cr_tenant", "tenant_id"),
        Index("idx_cr_doctor", "doctor_id"),
        Index("idx_cr_status", "tenant_id", "status"),
        Index("idx_cr_patient_date", "patient_id", "created_at"),
        Index("idx_cr_patient_signed", "patient_id", "status", "signed_at"),
        Index("idx_cr_visit", "patient_id", "visit_number"),
    )

# =====================================================================
# 025 · VITAL SIGNS
# =====================================================================
class VitalSign(Base):
    __tablename__ = "vital_signs"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    encounter_id = Column(BINARY(16), ForeignKey("encounters.id", ondelete="SET NULL"), nullable=True)
    clinical_record_id = Column(BINARY(16), ForeignKey("clinical_records.id", ondelete="SET NULL"), nullable=True)
    recorded_at = Column(DateTime, nullable=False, server_default=func.now())
    bp_systolic = Column(SmallInteger, nullable=True)
    bp_diastolic = Column(SmallInteger, nullable=True)
    heart_rate = Column(SmallInteger, nullable=True)
    resp_rate = Column(TINYINT, nullable=True)
    temperature = Column(DECIMAL(4,1), nullable=True)
    spo2 = Column(TINYINT, nullable=True)
    fio2 = Column(TINYINT, nullable=True)
    glucometria = Column(SmallInteger, nullable=True)
    weight = Column(DECIMAL(6,2), nullable=True)
    height = Column(DECIMAL(5,1), nullable=True)
    pain_scale_eva = Column(TINYINT, nullable=True)
    glasgow_ocular = Column(TINYINT, nullable=True)
    glasgow_verbal = Column(TINYINT, nullable=True)
    glasgow_motor = Column(TINYINT, nullable=True)
    glasgow_total = Column(TINYINT, nullable=True)
    perimetro_cefalico = Column(DECIMAL(4,1), nullable=True)
    flacc = Column(TINYINT, nullable=True)
    recorded_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_vs_patient", "patient_id", "recorded_at"),
        Index("idx_vs_tenant", "tenant_id"),
        Index("idx_vs_encounter", "encounter_id"),
        Index("idx_vs_record", "clinical_record_id"),
        Index("idx_vs_glasgow", "patient_id", "glasgow_total", "recorded_at"),
    )

# =====================================================================
# 027 · PHYSICAL EXAM FINDINGS
# =====================================================================
class PhysicalExamFinding(Base):
    __tablename__ = "physical_exam_findings"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    clinical_record_id = Column(BINARY(16), ForeignKey("clinical_records.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    system_name = Column(String(100), nullable=False)
    is_normal = Column(Boolean, nullable=True)
    findings = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_pef_record", "clinical_record_id"),
        Index("idx_pef_tenant", "tenant_id"),
        Index("idx_pef_system", "system_name"),
    )

# =====================================================================
# 028 · REVIEW OF SYSTEMS
# =====================================================================
class ReviewOfSystem(Base):
    __tablename__ = "review_of_systems"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    clinical_record_id = Column(BINARY(16), ForeignKey("clinical_records.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    system_name = Column(String(100), nullable=False)
    is_positive = Column(Boolean, nullable=True)
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_ros_record", "clinical_record_id"),
        Index("idx_ros_tenant", "tenant_id"),
    )

# =====================================================================
# 029 · CLINICAL PROBLEMS
# =====================================================================
class ClinicalProblem(Base):
    __tablename__ = "clinical_problems"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    clinical_record_id = Column(BINARY(16), ForeignKey("clinical_records.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    problem_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_cp_record", "clinical_record_id"),
        Index("idx_cp_tenant", "tenant_id"),
    )

# =====================================================================
# 030 · RECORD DIAGNOSES
# =====================================================================
class RecordDiagnosis(Base):
    __tablename__ = "record_diagnoses"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    encounter_id = Column(BINARY(16), ForeignKey("encounters.id", ondelete="SET NULL"), nullable=True)
    clinical_record_id = Column(BINARY(16), ForeignKey("clinical_records.id", ondelete="CASCADE"), nullable=True)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    clinical_problem_id = Column(BINARY(16), ForeignKey("clinical_problems.id", ondelete="SET NULL"), nullable=True)
    cie10_code = Column(String(10), nullable=False)
    cie10_description = Column(Text, nullable=False)
    diagnosis_type = Column(SQLEnum(DiagnosisType), nullable=False)
    is_first_time = Column(Boolean, nullable=False)
    is_primary_diagnosis = Column(Boolean, nullable=False)
    is_background = Column(Boolean, nullable=False)
    is_outpatient = Column(Boolean, nullable=False)
    status = Column(SQLEnum(DiagnosisStatus), nullable=False, default=DiagnosisStatus.active)
    severity = Column(SQLEnum(DiagnosisSeverity), nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_diag_encounter", "encounter_id"),
        Index("idx_diag_record", "clinical_record_id"),
        Index("idx_diag_tenant", "tenant_id"),
        Index("idx_diag_primary", "clinical_record_id", "is_primary_diagnosis"),
        Index("idx_diag_cie10", "cie10_code"),
    )

# =====================================================================
# 031 · RECORD PLANS
# =====================================================================
class RecordPlan(Base):
    __tablename__ = "record_plans"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    clinical_record_id = Column(BINARY(16), ForeignKey("clinical_records.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    plan_type = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_plans_record", "clinical_record_id"),
        Index("idx_plans_tenant", "tenant_id"),
    )

# =====================================================================
# 032 · CLINICAL NOTES
# =====================================================================
class ClinicalNote(Base):
    __tablename__ = "clinical_notes"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    admission_id = Column(BINARY(16), ForeignKey("patient_admissions.id", ondelete="SET NULL"), nullable=True)
    encounter_id = Column(BINARY(16), ForeignKey("encounters.id", ondelete="SET NULL"), nullable=True)
    clinical_record_id = Column(BINARY(16), ForeignKey("clinical_records.id", ondelete="SET NULL"), nullable=True)
    note_type = Column(SQLEnum(NoteType), nullable=False)
    content = Column(Text, nullable=False)
    authored_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    authored_by_name = Column(String(255), nullable=True)
    updated_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_closed = Column(Boolean, nullable=False, default=False)
    closed_at = Column(DateTime, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_notes_encounter", "encounter_id"),
        Index("idx_notes_patient", "patient_id"),
        Index("idx_notes_tenant", "tenant_id"),
        Index("idx_notes_admission", "admission_id"),
        Index("idx_notes_type", "note_type"),
    )

# =====================================================================
# 033 · CLINICAL SCALE RESULTS
# =====================================================================
class ClinicalScaleResult(Base):
    __tablename__ = "clinical_scale_results"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    clinical_record_id = Column(BINARY(16), ForeignKey("clinical_records.id", ondelete="SET NULL"), nullable=True)
    scale_name = Column(SQLEnum(ScaleName), nullable=False)
    total_score = Column(SmallInteger, nullable=True)
    risk_level = Column(String(50), nullable=True)
    details = Column(JSON, nullable=True)
    performed_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    performed_at = Column(DateTime, nullable=False, server_default=func.now())
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_scale_patient", "patient_id"),
        Index("idx_scale_tenant", "tenant_id"),
        Index("idx_scale_name", "scale_name"),
        Index("idx_scale_date", "patient_id", "scale_name", "performed_at"),
    )

# =====================================================================
# 040 · CLINICAL PROCEDURES
# =====================================================================
class ClinicalProcedure(Base):
    __tablename__ = "clinical_procedures"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    clinical_record_id = Column(BINARY(16), ForeignKey("clinical_records.id", ondelete="SET NULL"), nullable=True)
    consent_id = Column(BINARY(16), ForeignKey("patient_consents.id", ondelete="SET NULL"), nullable=True)
    procedure_name = Column(String(255), nullable=False)
    performed_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    performed_by_name = Column(String(255), nullable=True)
    performed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_proc_patient", "patient_id"),
        Index("idx_proc_tenant", "tenant_id"),
    )
