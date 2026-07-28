from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import create_engine, func, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.database import DATABASE_URL
from app.models.appointment import Appointment
from app.models.billing import Billing, BillingStatus
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.tenant import Tenant, TenantStatus, User, UserRole
from app.utils.password import normalize_password, pwd_context

TENANT_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


def _validate_tenant_id(tenant_id: str) -> str:
    value = tenant_id.strip()
    if not value or not TENANT_ID_PATTERN.fullmatch(value):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tenant_id must contain only lowercase letters, numbers, and underscores.",
        )
    return value


def _database_name(tenant_id: str) -> str:
    return f"salvio_{tenant_id}"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _schema_path() -> Path:
    return _project_root() / "salvio_schema_fixed.sql"


def _master_database_url() -> URL:
    if not DATABASE_URL:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="DATABASE_URL is not configured.")
    return make_url(DATABASE_URL)


def _server_database_url() -> str:
    return _master_database_url().set(database=None).render_as_string(hide_password=False)


def _tenant_database_url(db_name: str) -> str:
    return _master_database_url().set(database=db_name).render_as_string(hide_password=False)


def _iter_sql_statements(sql_text: str) -> Iterator[str]:
    buffer: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            statement = "\n".join(buffer).strip()
            if statement.endswith(";"):
                statement = statement[:-1].strip()
            if statement:
                yield statement
            buffer = []
    trailing = "\n".join(buffer).strip()
    if trailing:
        yield trailing


def _run_schema(db_name: str) -> None:
    schema_file = _schema_path()
    if not schema_file.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schema file not found: {schema_file}",
        )

    tenant_engine = create_engine(_tenant_database_url(db_name), pool_pre_ping=True)
    try:
        schema_sql = schema_file.read_text(encoding="utf-8")
        with tenant_engine.begin() as connection:
            for statement in _iter_sql_statements(schema_sql):
                connection.execute(text(statement))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Schema execution failed: {exc}") from exc
    finally:
        tenant_engine.dispose()


def _drop_database_if_exists(db_name: str) -> None:
    admin_engine = create_engine(_server_database_url(), pool_pre_ping=True)
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS `{db_name}`"))
    finally:
        admin_engine.dispose()


def _create_database(db_name: str) -> None:
    admin_engine = create_engine(_server_database_url(), pool_pre_ping=True)
    try:
        with admin_engine.begin() as connection:
            exists = connection.execute(text("SHOW DATABASES LIKE :db_name"), {"db_name": db_name}).scalar()
            if exists:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Database '{db_name}' already exists.",
                )
            connection.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}`"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database creation failed: {exc}") from exc
    finally:
        admin_engine.dispose()


def _seed_tenant_row_and_users(
    db_name: str,
    tenant_id: str,
    tenant_name: str,
    admin_email: str,
    admin_password: str,
    doctors: list[dict],
) -> int:
    tenant_engine = create_engine(_tenant_database_url(db_name), pool_pre_ping=True)
    tenant_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = tenant_session_factory()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant is None:
            tenant = Tenant(id=tenant_id, name=tenant_name, country="SV", status=TenantStatus.active)
            db.add(tenant)

        all_emails = [admin_email, *[doc["email"] for doc in doctors]]
        if len(all_emails) != len(set(all_emails)):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Duplicate email in the provisioning request.")

        existing = db.query(User).filter(User.email.in_(all_emails), User.deleted_at.is_(None)).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User '{existing.email}' already exists in database '{db_name}'.",
            )

        admin_user = User(
            id=uuid4().bytes,
            tenant_id=tenant_id,
            email=admin_email,
            hashed_password=pwd_context.hash(normalize_password(admin_password)),
            full_name=f"{tenant_name} Admin",
            role=UserRole.clinic_admin,
            is_active=True,
        )
        db.add(admin_user)

        for doc in doctors:
            db.add(
                User(
                    id=uuid4().bytes,
                    tenant_id=tenant_id,
                    email=doc["email"],
                    hashed_password=pwd_context.hash(normalize_password(doc["password"])),
                    full_name=doc["full_name"],
                    role=UserRole.doctor,
                    specialty=doc["specialty"],
                    is_active=True,
                )
            )

        db.commit()
        return len(doctors)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"User creation failed: {exc}") from exc
    finally:
        db.close()
        tenant_engine.dispose()


def create_tenant(
    tenant_id: str,
    tenant_name: str,
    admin_email: str,
    admin_password: str,
    doctors: list[dict] | None = None,
) -> dict:
    safe_tenant_id = _validate_tenant_id(tenant_id)
    db_name = _database_name(safe_tenant_id)
    normalized_doctors = [
        {
            "full_name": doc["full_name"].strip(),
            "specialty": doc["specialty"].strip(),
            "email": doc["email"].strip().lower(),
            "password": doc["password"],
        }
        for doc in (doctors or [])
    ]

    try:
        _create_database(db_name)
        _run_schema(db_name)
        doctors_created = _seed_tenant_row_and_users(
            db_name=db_name,
            tenant_id=safe_tenant_id,
            tenant_name=tenant_name.strip(),
            admin_email=admin_email.strip().lower(),
            admin_password=admin_password,
            doctors=normalized_doctors,
        )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_409_CONFLICT:
            _drop_database_if_exists(db_name)
        raise
    except Exception as exc:
        _drop_database_if_exists(db_name)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Tenant provisioning failed: {exc}") from exc

    return {
        "tenant_id": safe_tenant_id,
        "tenant_name": tenant_name.strip(),
        "admin_email": admin_email.strip().lower(),
        "db_name": db_name,
        "doctors_created": doctors_created,
        "message": "Tenant provisioned successfully.",
    }


# Databases that exist on the same MySQL server but are never real clinics, so
# they must never appear in the platform-admin tenant list.
_RESERVED_DB_NAMES = {"salvio_control", "salvio_tenant_template"}


def list_tenants(include_archived: bool = False) -> list[dict]:
    admin_engine = create_engine(_server_database_url(), pool_pre_ping=True)
    try:
        with admin_engine.connect() as connection:
            rows = connection.execute(text("SHOW DATABASES LIKE 'salvio\\_%'")).fetchall()
        db_names = [row[0] for row in rows if row[0] not in _RESERVED_DB_NAMES]
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Tenant listing failed: {exc}") from exc
    finally:
        admin_engine.dispose()

    tenants: list[dict] = []
    for db_name in db_names:
        tenant_id = db_name.removeprefix("salvio_")
        tenant_engine = create_engine(_tenant_database_url(db_name), pool_pre_ping=True)
        try:
            session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
            db: Session = session_factory()
            try:
                tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
                if tenant is not None and (include_archived or tenant.status != TenantStatus.archived):
                    tenants.append(
                        {
                            "tenant_id": tenant.id,
                            "name": tenant.name,
                            "country": tenant.country,
                            "status": tenant.status,
                            "created_at": tenant.created_at,
                        }
                    )
            finally:
                db.close()
        except SQLAlchemyError:
            # A database that doesn't have the current schema (or is mid-provisioning)
            # simply doesn't show up rather than failing the whole listing.
            continue
        finally:
            tenant_engine.dispose()

    tenants.sort(key=lambda t: t["created_at"], reverse=True)
    return tenants


def update_tenant(tenant_id: str, name: str | None, status: TenantStatus | None) -> dict:
    safe_tenant_id = _validate_tenant_id(tenant_id)
    db_name = _database_name(safe_tenant_id)

    admin_engine = create_engine(_server_database_url(), pool_pre_ping=True)
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(text("SHOW DATABASES LIKE :db_name"), {"db_name": db_name}).scalar()
    finally:
        admin_engine.dispose()
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")

    tenant_engine = create_engine(_tenant_database_url(db_name), pool_pre_ping=True)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = session_factory()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == safe_tenant_id).first()
        if tenant is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        if name is not None:
            tenant.name = name.strip()
        if status is not None:
            tenant.status = status
        db.commit()
        db.refresh(tenant)
        return {
            "tenant_id": tenant.id,
            "name": tenant.name,
            "country": tenant.country,
            "status": tenant.status,
            "created_at": tenant.created_at,
        }
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Tenant update failed: {exc}") from exc
    finally:
        db.close()
        tenant_engine.dispose()


def tenant_dashboard_stats() -> dict:
    """Grupo D: solo agregados (conteos/sumas) -- nunca contenido clinico
    individual de pacientes, segun lo ya aprobado. Mismo patron de fan-out
    que list_tenants() (una conexion desechable por BD de tenant, se
    salta silenciosamente cualquiera que falle -- no es peor que lo que ya
    hace list_tenants)."""
    admin_engine = create_engine(_server_database_url(), pool_pre_ping=True)
    try:
        with admin_engine.connect() as connection:
            rows = connection.execute(text("SHOW DATABASES LIKE 'salvio\\_%'")).fetchall()
        db_names = [row[0] for row in rows if row[0] not in _RESERVED_DB_NAMES]
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Dashboard aggregation failed: {exc}") from exc
    finally:
        admin_engine.dispose()

    tenants: list[dict] = []
    totals = {"patients": 0, "appointments": 0, "encounters": 0, "billing_pending": 0.0, "billing_paid": 0.0}

    for db_name in db_names:
        tenant_id = db_name.removeprefix("salvio_")
        tenant_engine = create_engine(_tenant_database_url(db_name), pool_pre_ping=True)
        try:
            session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
            db: Session = session_factory()
            try:
                tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
                if tenant is None:
                    continue
                patients_count = db.query(func.count(Patient.id)).filter(Patient.tenant_id == tenant_id, Patient.deleted_at.is_(None)).scalar() or 0
                appointments_count = db.query(func.count(Appointment.id)).filter(Appointment.tenant_id == tenant_id, Appointment.deleted_at.is_(None)).scalar() or 0
                encounters_count = db.query(func.count(Encounter.id)).filter(Encounter.tenant_id == tenant_id).scalar() or 0
                billing_pending = float(db.query(func.coalesce(func.sum(Billing.amount), 0)).filter(Billing.tenant_id == tenant_id, Billing.status == BillingStatus.pending).scalar() or 0)
                billing_paid = float(db.query(func.coalesce(func.sum(Billing.amount), 0)).filter(Billing.tenant_id == tenant_id, Billing.status == BillingStatus.paid).scalar() or 0)

                entry = {
                    "tenant_id": tenant.id,
                    "name": tenant.name,
                    "status": tenant.status,
                    "patients_count": patients_count,
                    "appointments_count": appointments_count,
                    "encounters_count": encounters_count,
                    "billing_pending": billing_pending,
                    "billing_paid": billing_paid,
                }
                tenants.append(entry)
                totals["patients"] += patients_count
                totals["appointments"] += appointments_count
                totals["encounters"] += encounters_count
                totals["billing_pending"] += billing_pending
                totals["billing_paid"] += billing_paid
            finally:
                db.close()
        except SQLAlchemyError:
            continue
        finally:
            tenant_engine.dispose()

    tenants.sort(key=lambda t: t["tenant_id"])
    return {"tenants": tenants, "totals": totals}
