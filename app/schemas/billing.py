from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.billing import BillingStatus, PaymentStatus
from app.schemas.common import ORMModel, StrippedStringMixin


class BillingBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    appointment_id: UUID | None = None
    amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    status: BillingStatus = BillingStatus.pending
    payment_method: str | None = Field(default=None, max_length=50)
    payment_date: datetime | None = None
    due_date: datetime | None = None
    invoice_number: str | None = Field(default=None, max_length=50)
    void_reason: str | None = None

    @model_validator(mode="after")
    def validate_void_reason(self):
        if self.status == BillingStatus.void and not self.void_reason:
            raise ValueError("se requiere void_reason cuando el estado de la factura es anulada.")
        return self


class BillingCreate(BillingBase):
    items: list["BillingItemCreate"] = Field(default_factory=list)


class BillingUpdate(StrippedStringMixin, ORMModel):
    status: BillingStatus | None = None
    payment_method: str | None = Field(default=None, max_length=50)
    payment_date: datetime | None = None
    invoice_number: str | None = Field(default=None, max_length=50)
    void_reason: str | None = None

    @model_validator(mode="after")
    def validate_void_reason(self):
        if self.status == BillingStatus.void and not self.void_reason:
            raise ValueError("se requiere void_reason para anular una factura.")
        return self


class BillingRead(BillingBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class BillingItemBase(StrippedStringMixin, ORMModel):
    billing_id: UUID | None = None
    tenant_id: str = Field(max_length=50)
    item_type: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=1, max_length=255)
    quantity: Decimal = Field(default=1, gt=0)
    unit_price: Decimal = Field(ge=0)
    discount_amount: Decimal = Field(default=0, ge=0)
    tax_amount: Decimal = Field(default=0, ge=0)
    total_amount: Decimal | None = Field(default=None, ge=0)
    service_date: datetime | None = None

    @model_validator(mode="after")
    def calculate_total(self):
        if self.total_amount is None:
            self.total_amount = (self.quantity * self.unit_price) - self.discount_amount + self.tax_amount
        if self.total_amount < 0:
            raise ValueError("total_amount no puede ser negativo.")
        return self


class BillingItemCreate(BillingItemBase):
    pass


class BillingItemRead(BillingItemBase):
    id: UUID
    billing_id: UUID
    created_at: datetime


class PaymentBase(StrippedStringMixin, ORMModel):
    billing_id: UUID
    tenant_id: str = Field(max_length=50)
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    payment_method: str = Field(min_length=1, max_length=50)
    reference_number: str | None = Field(default=None, max_length=100)
    status: PaymentStatus = PaymentStatus.pending
    paid_at: datetime | None = None
    processed_by: UUID | None = None
    notes: str | None = None


class PaymentCreate(PaymentBase):
    pass


class PaymentRead(PaymentBase):
    id: UUID
    created_at: datetime


class BillingDetail(BillingRead):
    items: list[BillingItemRead] = Field(default_factory=list)
    payments: list[PaymentRead] = Field(default_factory=list)
