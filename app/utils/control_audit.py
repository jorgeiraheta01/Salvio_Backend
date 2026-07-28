from typing import Any
from uuid import UUID, uuid4
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.control_audit import ControlAuditLog


def _uuid_to_bytes(value: Any) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, UUID):
        return value.bytes
    return UUID(str(value)).bytes


def log_control_audit(
    db: Session,
    *,
    admin_id: Any,
    action: str,
    table_name: str,
    tenant_id: str | None = None,
    record_id: Any = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Registra una accion del owner de la plataforma en salvio_control.

    `db` debe ser una sesion abierta contra get_control_engine() -- el
    caller es responsable de hacer commit (mismo patron que log_audit() de
    tenant, para no forzar un commit prematuro si la accion todavia tiene
    mas pasos pendientes en la misma transaccion).
    """
    db.add(
        ControlAuditLog(
            id=uuid4().bytes,
            admin_id=_uuid_to_bytes(admin_id),
            tenant_id=tenant_id,
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
