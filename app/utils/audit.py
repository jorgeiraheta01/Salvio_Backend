from typing import Any
from uuid import UUID, uuid4
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def _uuid_to_bytes(value: Any) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, UUID):
        return value.bytes
    return UUID(str(value)).bytes


def log_audit(
    db: Session,
    *,
    tenant_id: str | None,
    user_id: Any,
    action: str,
    table_name: str,
    record_id: Any = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    db.add(
        AuditLog(
            id=uuid4().bytes,
            tenant_id=tenant_id,
            user_id=_uuid_to_bytes(user_id),
            action=action,
            table_name=table_name,
            record_id=_uuid_to_bytes(record_id),
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.now(timezone.utc),
        )
    )
