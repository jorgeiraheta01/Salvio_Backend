from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from app.models.wa import WaMessageStatus
from app.schemas.common import ORMModel, StrippedStringMixin


class WaMessageBase(StrippedStringMixin, ORMModel):
    patient_id: UUID
    tenant_id: str = Field(max_length=50)
    appointment_id: UUID | None = None
    message_type: str | None = Field(default=None, max_length=50)
    template_name: str | None = Field(default=None, max_length=100)
    status: WaMessageStatus = WaMessageStatus.pending
    error_message: str | None = None
    sent_at: datetime | None = None
    has_whatsapp_consent: bool = True

    @model_validator(mode="after")
    def require_consent(self):
        if not self.has_whatsapp_consent:
            raise ValueError("se requiere consentimiento explicito del paciente antes de enviar mensajes de WhatsApp.")
        if self.status == WaMessageStatus.failed and not self.error_message:
            raise ValueError("error_message es obligatorio cuando el estado de WhatsApp es fallido.")
        return self


class WaMessageCreate(WaMessageBase):
    pass


class WaMessageUpdate(StrippedStringMixin, ORMModel):
    status: WaMessageStatus | None = None
    error_message: str | None = None
    sent_at: datetime | None = None

    @model_validator(mode="after")
    def require_error_on_failed(self):
        if self.status == WaMessageStatus.failed and not self.error_message:
            raise ValueError("error_message es obligatorio cuando el estado de WhatsApp es fallido.")
        return self


class WaMessageRead(WaMessageBase):
    id: UUID
    created_at: datetime


class WaFallbackAttempt(ORMModel):
    channel: str = Field(pattern=r"^(whatsapp|email|sms)$")
    status: str = Field(pattern=r"^(pending|sent|failed)$")
    error_message: str | None = None
    attempted_at: datetime | None = None
