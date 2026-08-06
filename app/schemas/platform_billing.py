from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.models.platform_billing import ChargeStatus
from app.schemas.common import ORMModel


class PlatformChargeCreate(ORMModel):
    tenant_id: str = Field(min_length=1, max_length=50)
    period_label: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0)
    due_date: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


class PlatformChargeUpdate(ORMModel):
    status: ChargeStatus


class PlatformChargeRead(ORMModel):
    id: UUID
    invoice_number: int
    tenant_id: str
    period_label: str
    amount: Decimal
    currency: str
    status: ChargeStatus
    due_date: datetime | None
    paid_at: datetime | None
    notes: str | None
    created_at: datetime


class PlatformChargeTotals(ORMModel):
    pending: Decimal
    paid: Decimal
    void: Decimal


class PlatformChargesResponse(ORMModel):
    charges: list[PlatformChargeRead]
    totals: PlatformChargeTotals
