from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum, ForeignKey, DECIMAL, Text, Index
from sqlalchemy.dialects.mysql import BINARY
from sqlalchemy.sql import func
from app.database import Base
import enum

class BillingStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    void = "void"
    refunded = "refunded"

class PaymentStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    refunded = "refunded"
    void = "void"

class Billing(Base):
    __tablename__ = "billing"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    patient_id = Column(BINARY(16), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    appointment_id = Column(BINARY(16), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True)
    amount = Column(DECIMAL(10,2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    status = Column(SQLEnum(BillingStatus), nullable=False, default="pending")
    payment_method = Column(String(50), nullable=True)
    payment_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    invoice_number = Column(String(50), nullable=True)
    void_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_billing_patient", "patient_id"),
        Index("idx_billing_tenant", "tenant_id"),
        Index("idx_billing_status", "tenant_id", "status", "created_at"),
        Index("uq_billing_invoice", "tenant_id", "invoice_number", unique=True),
    )

class BillingItem(Base):
    __tablename__ = "billing_items"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    billing_id = Column(BINARY(16), ForeignKey("billing.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    item_type = Column(String(100), nullable=True)
    description = Column(String(255), nullable=False)
    quantity = Column(DECIMAL(10,2), nullable=False, default=1)
    unit_price = Column(DECIMAL(10,2), nullable=False)
    discount_amount = Column(DECIMAL(10,2), nullable=False, default=0)
    tax_amount = Column(DECIMAL(10,2), nullable=False, default=0)
    total_amount = Column(DECIMAL(10,2), nullable=False)
    service_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_billing_items_billing", "billing_id"),
        Index("idx_billing_items_tenant", "tenant_id"),
    )

class Payment(Base):
    __tablename__ = "payments"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    billing_id = Column(BINARY(16), ForeignKey("billing.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    amount = Column(DECIMAL(10,2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    payment_method = Column(String(50), nullable=False)
    reference_number = Column(String(100), nullable=True)
    status = Column(SQLEnum(PaymentStatus), nullable=False, default="pending")
    paid_at = Column(DateTime, nullable=True)
    processed_by = Column(BINARY(16), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_payments_billing", "billing_id"),
        Index("idx_payments_tenant", "tenant_id"),
        Index("idx_payments_status", "tenant_id", "status", "created_at"),
    )
