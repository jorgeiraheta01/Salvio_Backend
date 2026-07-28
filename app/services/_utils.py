from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.utils.audit import log_audit


def uuid_bytes(value: UUID | str | bytes | bytearray | None) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, UUID):
        return value.bytes
    return UUID(str(value)).bytes


def bytes_uuid(value: bytes | bytearray | UUID | str | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    if isinstance(value, (bytes, bytearray)):
        return UUID(bytes=bytes(value))
    return UUID(str(value))


def new_uuid_bytes() -> bytes:
    return uuid4().bytes


def model_to_dict(obj: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        if isinstance(value, (bytes, bytearray)) and len(value) == 16:
            data[column.name] = str(UUID(bytes=bytes(value)))
        elif isinstance(value, (datetime, date)):
            data[column.name] = value.isoformat()
        elif isinstance(value, Decimal):
            data[column.name] = str(value)
        elif isinstance(value, Enum):
            data[column.name] = value.value
        else:
            data[column.name] = value
    return data


def data_for_model(data: Any, model: Any, *, exclude: set[str] | None = None, tenant_id: str | None = None) -> dict[str, Any]:
    exclude = exclude or set()
    payload = data.model_dump(exclude_unset=True, exclude=exclude)
    if tenant_id is not None and "tenant_id" in model.__table__.columns:
        payload["tenant_id"] = tenant_id
    columns = set(model.__table__.columns.keys())
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in columns:
            continue
        # UUID-typed fields must become raw bytes for BINARY(16) columns regardless of
        # the field's name — a name-based whitelist (endswith("_id") / hardcoded set)
        # missed columns like ordered_by/performed_by/uploaded_by/prescribed_by/etc,
        # leaving them as UUID objects that fail at INSERT time.
        if isinstance(value, UUID):
            result[key] = uuid_bytes(value)
        elif key != "tenant_id" and (key.endswith("_id") or key in {"id", "user_id", "record_id", "signed_by", "recorded_by", "created_by"}):
            result[key] = uuid_bytes(value)
        else:
            result[key] = value
    if "id" in columns and "id" not in result:
        result["id"] = new_uuid_bytes()
    return result


def commit_or_409(db: Session, detail: str = "Duplicate or constraint conflict.") -> None:
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


def audit(
    db: Session,
    *,
    user_id: bytes,
    tenant_id: str,
    action: str,
    table_name: str,
    record_id: bytes | UUID | None,
    old_values: dict | None = None,
    new_values: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    log_audit(
        db,
        user_id=user_id,
        tenant_id=tenant_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def not_found(detail: str = "Resource not found.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
