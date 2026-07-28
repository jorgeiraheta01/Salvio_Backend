from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.tenant import User
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


def model_to_dict(obj: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        if isinstance(value, (bytes, bytearray)) and len(value) == 16:
            data[column.name] = UUID(bytes=bytes(value))
        else:
            data[column.name] = value
    return data


def clean_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray)) and len(value) == 16:
        return str(UUID(bytes=bytes(value)))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (set, frozenset)):
        # Columnas SET de MySQL se leen como set[str] -- no serializable a
        # JSON tal cual (rompia silenciosamente cualquier audit_mutation
        # sobre una fila con una columna SET).
        return sorted(value)
    return value


def audit_values(data: dict[str, Any]) -> dict[str, Any]:
    return {key: clean_value(value) for key, value in data.items()}


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
        # See app/services/_utils.py:data_for_model for why we check the value's
        # actual type instead of relying solely on a name-based whitelist.
        if isinstance(value, UUID):
            result[key] = uuid_bytes(value)
        elif key != "tenant_id" and (key.endswith("_id") or key in {"id", "user_id", "record_id", "signed_by", "recorded_by", "created_by"}):
            result[key] = uuid_bytes(value)
        else:
            result[key] = value
    return result


def data_for_create(data: Any, model: Any, *, exclude: set[str] | None = None, tenant_id: str | None = None) -> dict[str, Any]:
    payload = data_for_model(data, model, exclude=exclude, tenant_id=tenant_id)
    if "id" in model.__table__.columns and "id" not in payload:
        payload["id"] = uuid4().bytes
    return payload


def get_by_id_or_404(db: Session, model: Any, record_id: UUID, tenant_id: str, *, include_deleted: bool = False) -> Any:
    query = db.query(model).filter(model.id == uuid_bytes(record_id), model.tenant_id == tenant_id)
    if not include_deleted and hasattr(model, "deleted_at"):
        query = query.filter(model.deleted_at.is_(None))
    obj = query.first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")
    return obj


def ensure_patient_exists(db: Session, patient_model: Any, patient_id: UUID, tenant_id: str) -> Any:
    patient = (
        db.query(patient_model)
        .filter(patient_model.id == uuid_bytes(patient_id), patient_model.tenant_id == tenant_id, patient_model.deleted_at.is_(None))
        .first()
    )
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")
    return patient


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def audit_mutation(
    db: Session,
    request: Request,
    current_user: User,
    *,
    action: str,
    table_name: str,
    record_id: Any,
    old_values: dict | None = None,
    new_values: dict | None = None,
) -> None:
    log_audit(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_values=audit_values(old_values or {}),
        new_values=audit_values(new_values or {}),
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


def commit_or_409(db: Session, detail: str = "Duplicate or constraint conflict.") -> None:
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


def next_mrn(db: Session, patient_model: Any, tenant_id: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"MRN-{today}-"
    count = (
        db.query(func.count(patient_model.id))
        .filter(patient_model.tenant_id == tenant_id, patient_model.medical_record_number.like(f"{prefix}%"))
        .scalar()
        or 0
    )
    return f"{prefix}{count + 1:04d}"


def patient_search_filter(patient_model: Any, q: str):
    pattern = f"%{q}%"
    return or_(
        patient_model.first_name.ilike(pattern),
        patient_model.last_name.ilike(pattern),
        patient_model.dui.ilike(pattern),
        patient_model.medical_record_number.ilike(pattern),
    )
