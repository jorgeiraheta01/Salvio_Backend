from sqlalchemy import Column, String, Boolean, DateTime, Date, Enum as SQLEnum, ForeignKey, Text, Index, DECIMAL, SmallInteger, Integer
from sqlalchemy.dialects.mysql import BINARY
from sqlalchemy.sql import func
from app.database import Base
import enum

class PrescriptionStatus(str, enum.Enum):
    pending_override = "pending_override"
    active = "active"
    dispensed = "dispensed"
    cancelled = "cancelled"

class PrescriptionItemStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    completed = "completed"
    substituted = "substituted"

class Prescription(Base):
    __tablename__ = "prescriptions"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    encounter_id = Column(BINARY(16), ForeignKey("encounters.id", ondelete="SET NULL"), nullable=True)
    clinical_record_id = Column(BINARY(16), ForeignKey("clinical_records.id", ondelete="SET NULL"), nullable=True)
    prescribed_by = Column(BINARY(16), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    prescribed_by_name = Column(String(255), nullable=False)
    prescribed_at = Column(DateTime, nullable=False, server_default=func.now())
    pdf_url = Column(String(500), nullable=True)
    status = Column(SQLEnum(PrescriptionStatus), nullable=False, default="active")
    updated_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_rx_encounter", "encounter_id"),
        Index("idx_rx_patient", "patient_id"),
        Index("idx_rx_tenant", "tenant_id"),
        Index("idx_rx_status", "tenant_id", "status"),
    )


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    prescription_id = Column(BINARY(16), ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    medication_name = Column(String(255), nullable=False)
    medication_code = Column(String(50), nullable=True)
    concentration = Column(String(100), nullable=True)
    pharmaceutical_form = Column(String(100), nullable=True)
    dose = Column(String(100), nullable=True)
    frequency = Column(String(100), nullable=True)
    duration = Column(String(100), nullable=True)
    route = Column(String(100), nullable=True)
    quantity = Column(DECIMAL(10,2), nullable=True)
    refills = Column(SmallInteger, nullable=False, default=0)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    indication = Column(String(255), nullable=True)
    instructions = Column(Text, nullable=True)
    status = Column(SQLEnum(PrescriptionItemStatus), nullable=False, default="active")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_prescription_item", "prescription_id"),
        Index("idx_rx_item_tenant", "tenant_id"),
        Index("idx_rx_item_status", "tenant_id", "status"),
    )
