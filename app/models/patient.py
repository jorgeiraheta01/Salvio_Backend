from sqlalchemy import Column, String, Boolean, DateTime, Date, Enum as SQLEnum, ForeignKey, Text, DECIMAL, SmallInteger, Index
from sqlalchemy.dialects.mysql import BINARY, TINYINT
from sqlalchemy.sql import func
from app.database import Base
import enum

# =====================================================================
# ENUMS específicos de patients
# =====================================================================
class Gender(str, enum.Enum):
    male = "male"
    female = "female"
    other = "other"

class InsuranceType(str, enum.Enum):
    particular = "particular"
    ss_pensionado = "ss_pensionado"
    ss_cotizante = "ss_cotizante"
    ss_beneficiario = "ss_beneficiario"
    red_publica = "red_publica"
    privado = "privado"
    ninguno = "ninguno"
    otro = "otro"

class Severity(str, enum.Enum):
    mild = "mild"
    moderate = "moderate"
    severe = "severe"
    life_threatening = "life_threatening"

class Smoking(str, enum.Enum):
    never = "never"
    former = "former"
    current = "current"

class Alcohol(str, enum.Enum):
    never = "never"
    occasional = "occasional"
    daily = "daily"

class RhFactor(str, enum.Enum):
    positive = "positive"
    negative = "negative"
    unknown = "unknown"

class DeliveryRoute(str, enum.Enum):
    vaginal = "vaginal"
    cesarean = "cesarean"
    forceps = "forceps"

class PatientConsentType(str, enum.Enum):
    treatment = "treatment"
    surgery = "surgery"
    anesthesia = "anesthesia"
    data = "data"
    whatsapp = "whatsapp"

class ImmunizationStatus(str, enum.Enum):
    applied = "applied"
    pending = "pending"
    refused = "refused"
    contraindicated = "contraindicated"

# =====================================================================
# 006 · PATIENTS
# =====================================================================
class Patient(Base):
    __tablename__ = "patients"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    medical_record_number = Column(String(50), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(SQLEnum(Gender), nullable=False)
    dui = Column(String(10), nullable=True)   # ← unique global eliminado, ahora único por tenant
    nit = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(30), nullable=True)
    address = Column(Text, nullable=True)
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(30), nullable=True)
    emergency_contact_relationship = Column(String(100), nullable=True)
    insurance_type = Column(SQLEnum(InsuranceType), nullable=False)
    insurance_number = Column(String(50), nullable=True)
    attention_number = Column(String(50), nullable=True)
    last_employer = Column(String(255), nullable=True)
    work_phone = Column(String(30), nullable=True)
    last_occupation = Column(String(200), nullable=True)
    last_contribution_period = Column(String(50), nullable=True)
    last_work_date = Column(Date, nullable=True)
    # True cuando el registro se creo por una referencia cross-tenant (ver
    # POST /referrals/cross-tenant/{id}/import-patient) -- explicito en vez
    # de inferirlo del prefijo "REF-" en medical_record_number.
    is_referred = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("uq_patients_mrn_tenant", "tenant_id", "medical_record_number", unique=True),
        Index("uq_patient_dui_tenant", "tenant_id", "dui", unique=True),   # ← nuevo índice único compuesto
        Index("idx_patients_tenant", "tenant_id"),
        Index("idx_patients_tenant_insurance", "tenant_id", "insurance_type"),
        Index("idx_patients_name", "last_name", "first_name"),
        Index("idx_patients_deleted", "deleted_at"),
    )

# =====================================================================
# El resto del archivo (PatientAllergy, PatientMedication, PatientPhysiologicalHx,
# PatientChronicDisease, PatientSurgery, PatientHospitalizationHx, PatientFamilyHx,
# PatientGynecologicalHx, PatientSocialHx, PatientPerinatalHx, PatientDevelopmentHx,
# PatientConsent) se mantiene IDÉNTICO a tu versión original.
# Solo se muestra hasta PatientConsent para que copies todo lo que sigue.
# =====================================================================

# 007 · PATIENT ALLERGIES
class PatientAllergy(Base):
    __tablename__ = "patient_allergies"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    allergen = Column(String(255), nullable=False)
    reaction = Column(String(255), nullable=True)
    severity = Column(SQLEnum(Severity), nullable=False)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_allergies_patient", "patient_id"),
        Index("idx_allergies_tenant", "tenant_id"),
    )

# 008 · PATIENT MEDICATIONS (actuales)
class PatientMedication(Base):
    __tablename__ = "patient_medications"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    medication_name = Column(String(255), nullable=False)
    dose = Column(String(100), nullable=True)
    frequency = Column(String(100), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    prescribed_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    prescribed_by_name = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_meds_patient", "patient_id"),
        Index("idx_meds_tenant", "tenant_id"),
        Index("idx_meds_active", "patient_id", "is_active"),
    )

# 009 · PATIENT PHYSIOLOGICAL HISTORY
class PatientPhysiologicalHx(Base):
    __tablename__ = "patient_physiological_hx"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, unique=True)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    blood_type = Column(String(5), nullable=True)
    rh_factor = Column(SQLEnum(RhFactor), nullable=True)
    smoking = Column(SQLEnum(Smoking), nullable=False, default="never")
    alcohol = Column(SQLEnum(Alcohol), nullable=False, default="never")
    drugs = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("idx_physiohx_tenant", "tenant_id"),)

# 010 · PATIENT CHRONIC DISEASES
class PatientChronicDisease(Base):
    __tablename__ = "patient_chronic_diseases"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    disease_name = Column(String(255), nullable=False)
    cie10_code = Column(String(10), nullable=True)
    diagnosis_date = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_chronic_patient", "patient_id"),
        Index("idx_chronic_tenant", "tenant_id"),
    )

# 011 · PATIENT SURGERIES
class PatientSurgery(Base):
    __tablename__ = "patient_surgeries"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    surgery_name = Column(String(255), nullable=False)
    surgery_date = Column(Date, nullable=True)
    hospital = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_surgeries_patient", "patient_id"),
        Index("idx_surgeries_tenant", "tenant_id"),
    )

# 012 · PATIENT HOSPITALIZATIONS HISTORY
class PatientHospitalizationHx(Base):
    __tablename__ = "patient_hospitalizations_hx"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    admission_date = Column(Date, nullable=False)
    discharge_date = Column(Date, nullable=True)
    reason = Column(Text, nullable=True)
    hospital = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_hosphx_patient", "patient_id"),
        Index("idx_hosphx_tenant", "tenant_id"),
    )

# 013 · PATIENT FAMILY HISTORY
class PatientFamilyHx(Base):
    __tablename__ = "patient_family_hx"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    relationship = Column(String(100), nullable=True)
    condition_name = Column(String(255), nullable=True)
    cie10_code = Column(String(10), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_familyhx_patient", "patient_id"),
        Index("idx_familyhx_tenant", "tenant_id"),
    )

# 014 · PATIENT GYNECOLOGICAL HISTORY
class PatientGynecologicalHx(Base):
    __tablename__ = "patient_gynecological_hx"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, unique=True)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    menarche_age = Column(TINYINT, nullable=True)
    last_menstrual_period = Column(Date, nullable=True)
    pregnancies = Column(TINYINT, nullable=True)
    deliveries = Column(TINYINT, nullable=True)
    abortions = Column(TINYINT, nullable=True)
    contraceptive_method = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_gynohx_tenant", "tenant_id"),)

# 015 · PATIENT SOCIAL HISTORY
class PatientSocialHx(Base):
    __tablename__ = "patient_social_hx"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, unique=True)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    occupation = Column(String(255), nullable=True)
    living_conditions = Column(Text, nullable=True)
    housing_type = Column(String(100), nullable=True)
    has_water = Column(Boolean, nullable=True)
    has_sewer = Column(Boolean, nullable=True)
    has_electricity = Column(Boolean, nullable=True)
    pets = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_socialhx_tenant", "tenant_id"),)

# 016 · PATIENT PERINATAL HISTORY
class PatientPerinatalHx(Base):
    __tablename__ = "patient_perinatal_hx"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, unique=True)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    gestational_weeks = Column(TINYINT, nullable=True)
    prenatal_controls = Column(TINYINT, nullable=True)
    delivery_route = Column(SQLEnum(DeliveryRoute), nullable=True)
    birth_weight = Column(DECIMAL(6,2), nullable=True)
    birth_length = Column(DECIMAL(5,1), nullable=True)
    head_circumference = Column(DECIMAL(5,1), nullable=True)
    apgar_1min = Column(TINYINT, nullable=True)
    apgar_5min = Column(TINYINT, nullable=True)
    apgar_10min = Column(TINYINT, nullable=True)
    ballard_weeks = Column(TINYINT, nullable=True)
    silverman_retractions = Column(TINYINT, nullable=True)
    silverman_cyanosis = Column(TINYINT, nullable=True)
    silverman_grunting = Column(TINYINT, nullable=True)
    silverman_breathing = Column(TINYINT, nullable=True)
    silverman_auscultation = Column(TINYINT, nullable=True)
    silverman_total = Column(TINYINT, nullable=True)
    nicu_admission = Column(Boolean, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_perinatal_tenant", "tenant_id"),)

# 018 · PATIENT DEVELOPMENT HISTORY (resumen)
class PatientDevelopmentHx(Base):
    __tablename__ = "patient_development_hx"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, unique=True)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    walking_age_months = Column(DECIMAL(5,1), nullable=True)
    first_words_age_months = Column(DECIMAL(5,1), nullable=True)
    toilet_training_age_months = Column(DECIMAL(5,1), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_devhx_tenant", "tenant_id"),)

# 020 · PATIENT CONSENTS
class PatientConsent(Base):
    __tablename__ = "patient_consents"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    consent_type = Column(SQLEnum(PatientConsentType), nullable=False)
    consent_text = Column(Text, nullable=False)
    signed_at = Column(DateTime, nullable=False, server_default=func.now())
    signed_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    pdf_url = Column(String(500), nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_consents_patient", "patient_id"),
        Index("idx_consents_tenant", "tenant_id"),
        Index("idx_consents_type", "consent_type"),
    )

class PatientImmunization(Base):
    __tablename__ = "patient_immunizations"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    vaccine_name = Column(String(255), nullable=False)
    dose_number = Column(String(50), nullable=True)
    lot_number = Column(String(100), nullable=True)
    applied_at = Column(Date, nullable=True)
    next_due_at = Column(Date, nullable=True)
    applied_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(SQLEnum(ImmunizationStatus), nullable=False, default="applied")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_immun_patient", "patient_id"),
        Index("idx_immun_tenant", "tenant_id"),
        Index("idx_immun_due", "tenant_id", "next_due_at"),
    )

class PatientGrowthMeasurement(Base):
    __tablename__ = "patient_growth_measurements"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    clinical_record_id = Column(BINARY(16), ForeignKey("clinical_records.id", ondelete="SET NULL"), nullable=True)
    measured_at = Column(DateTime, nullable=False, server_default=func.now())
    weight = Column(DECIMAL(6,2), nullable=True)
    height = Column(DECIMAL(5,1), nullable=True)
    head_circumference = Column(DECIMAL(5,1), nullable=True)
    bmi = Column(DECIMAL(5,2), nullable=True)
    weight_percentile = Column(DECIMAL(5,2), nullable=True)
    height_percentile = Column(DECIMAL(5,2), nullable=True)
    bmi_percentile = Column(DECIMAL(5,2), nullable=True)
    recorded_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_growth_patient", "patient_id", "measured_at"),
        Index("idx_growth_tenant", "tenant_id"),
        Index("idx_growth_record", "clinical_record_id"),
    )
