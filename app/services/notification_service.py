from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.patient import PatientConsent, PatientConsentType
from app.models.wa import WaMessage, WaMessageStatus
from app.schemas.wa import WaMessageCreate
from app.services._utils import audit, commit_or_409, data_for_model, model_to_dict, new_uuid_bytes


def check_whatsapp_consent(db: Session, patient_id: bytes) -> bool:
    return (
        db.query(PatientConsent)
        .filter(
            PatientConsent.patient_id == patient_id,
            PatientConsent.consent_type == PatientConsentType.whatsapp,
            PatientConsent.revoked_at.is_(None),
        )
        .first()
        is not None
    )


def enqueue_whatsapp_message(db: Session, tenant_id: str, data: WaMessageCreate, user_id: bytes) -> WaMessage:
    if not check_whatsapp_consent(db, data.patient_id.bytes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El paciente no ha dado consentimiento para WhatsApp")
    message = WaMessage(**data_for_model(data, WaMessage, exclude={"has_whatsapp_consent"}, tenant_id=tenant_id))
    message.id = new_uuid_bytes()
    message.status = WaMessageStatus.pending
    db.add(message)
    db.flush()
    # TODO Bloque 6: send_whatsapp_task.delay(str(UUID(bytes=message.id)))
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="wa_messages", record_id=message.id, new_values=model_to_dict(message))
    commit_or_409(db)
    db.refresh(message)
    return message
