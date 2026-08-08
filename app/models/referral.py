from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum, ForeignKey, Text, Index
from sqlalchemy.dialects.mysql import BINARY
from sqlalchemy.sql import func
from app.database import Base
import enum

class InterconsultStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    completed = "completed"
    rejected = "rejected"

class ReferralType(str, enum.Enum):
    internal = "internal"
    internal_transfer = "internal_transfer"
    cross_tenant = "cross_tenant"
    public = "public"

class ReferralStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    completed = "completed"
    rejected = "rejected"

class Interconsult(Base):
    __tablename__ = "interconsults"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    clinical_record_id = Column(BINARY(16), ForeignKey("clinical_records.id", ondelete="SET NULL"), nullable=True)
    requesting_doctor = Column(BINARY(16), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    requesting_doctor_name = Column(String(255), nullable=False)
    consulting_specialty = Column(String(100), nullable=False)
    reason = Column(Text, nullable=True)
    requested_at = Column(DateTime, nullable=False, server_default=func.now())
    response = Column(Text, nullable=True)
    responded_at = Column(DateTime, nullable=True)
    status = Column(SQLEnum(InterconsultStatus), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_ic_patient", "patient_id"),
        Index("idx_ic_tenant", "tenant_id"),
        Index("idx_ic_status", "tenant_id", "status"),
    )

class Referral(Base):
    __tablename__ = "referrals"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    clinical_record_id = Column(BINARY(16), ForeignKey("clinical_records.id", ondelete="SET NULL"), nullable=True)
    referral_type = Column(SQLEnum(ReferralType), nullable=False)
    source_service = Column(String(100), nullable=True)
    destination_area = Column(String(100), nullable=True)
    transfer_reason = Column(Text, nullable=True)
    referred_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    referred_by_name = Column(String(255), nullable=True)
    target_tenant_id = Column(String(50), nullable=True)
    # Sin FK real: el medico destino vive en la base de otro tenant. Se
    # capturan al elegirlo en el buscador de la red (ver /network-doctors).
    target_doctor_id = Column(BINARY(16), nullable=True)
    target_doctor_name = Column(String(255), nullable=True)
    status = Column(SQLEnum(ReferralStatus), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_ref_patient", "patient_id"),
        Index("idx_ref_tenant", "tenant_id"),
        Index("idx_ref_type", "tenant_id", "referral_type"),
        Index("idx_ref_status", "tenant_id", "status"),
    )

class PublicAccessToken(Base):
    __tablename__ = "public_access_tokens"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    referral_id = Column(BINARY(16), ForeignKey("referrals.id", ondelete="CASCADE"), nullable=True)
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    clinical_record_id = Column(BINARY(16), ForeignKey("clinical_records.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_pat_expires", "expires_at"),)