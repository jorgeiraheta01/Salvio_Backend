import enum

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.mysql import BINARY
from sqlalchemy.sql import func

from app.database import Base


class EncounterStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    closed = "closed"


class ClinicalOrderStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class Encounter(Base):
    __tablename__ = "encounters"

    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    appointment_id = Column(BINARY(16), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True)
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    doctor_id = Column(BINARY(16), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status = Column(SQLEnum(EncounterStatus), nullable=False, default=EncounterStatus.active)
    chief_complaint = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_encounter_tenant", "tenant_id"),
        Index("idx_encounter_patient", "patient_id"),
        Index("idx_encounter_appointment", "appointment_id"),
        Index("idx_encounter_doctor_status", "tenant_id", "doctor_id", "status"),
    )


class ClinicalOrder(Base):
    __tablename__ = "clinical_orders"

    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    encounter_id = Column(BINARY(16), ForeignKey("encounters.id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    ordered_by = Column(BINARY(16), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    order_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(SQLEnum(ClinicalOrderStatus), nullable=False, default=ClinicalOrderStatus.active)
    scheduled_for = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_clinical_orders_tenant", "tenant_id"),
        Index("idx_clinical_orders_encounter", "encounter_id"),
        Index("idx_clinical_orders_status", "tenant_id", "status"),
    )
