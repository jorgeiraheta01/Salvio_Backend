import enum

from sqlalchemy import BINARY, Boolean, Column, DateTime, DECIMAL, Enum as SQLEnum, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.models.platform_admin import ControlBase


class ChargeStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    void = "void"


class PlatformCharge(ControlBase):
    """Cobro del dueno de la plataforma a UNA clinica (SaaS billing) --
    vive en salvio_control, no en la BD de la clinica, porque es facturacion
    de la plataforma hacia el cliente (la clinica), no facturacion clinica
    de paciente->clinica (eso ya existe como Billing dentro de cada tenant).
    tenant_id es solo un string (no FK): cada clinica vive en su propia BD
    fisica (ADR-01), asi que no hay integridad referencial real posible
    entre bases distintas -- mismo patron que control_audit.tenant_id."""

    __tablename__ = "platform_charges"

    id = Column(BINARY(16), primary_key=True)
    tenant_id = Column(String(50), nullable=False)
    # Numero correlativo mostrado en la factura PDF (distinto del id BINARY,
    # que no es apto para mostrarle a un cliente) -- por CLINICA, no global:
    # cada tenant tiene su propia secuencia 1, 2, 3... AUTO_INCREMENT de
    # MySQL es siempre global a la tabla, asi que esto se calcula a mano en
    # create_charge() (MAX(invoice_number) WHERE tenant_id=X + 1) en vez de
    # dejarselo a la BD.
    invoice_number = Column(Integer, nullable=False)
    period_label = Column(String(100), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    status = Column(SQLEnum(ChargeStatus), nullable=False, default=ChargeStatus.pending)
    due_date = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(BINARY(16), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("tenant_id", "invoice_number", name="uq_platform_charges_tenant_invoice"),)
