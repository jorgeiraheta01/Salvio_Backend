from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import bindparam, create_engine, func, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.database import DATABASE_URL
from app.models.appointment import Appointment, AppointmentStatus
from app.models.audit import AuditLog
from app.models.billing import Billing, BillingStatus
from app.models.encounter import Encounter
from app.models.lab import LabOrder
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.tenant import Tenant, TenantModuleFlag, TenantStatus, User, UserRole
from app.utils.password import normalize_password, pwd_context

# Modulos activables por clinica (Fase 1 de "Inactivar" en el panel del
# dueno) -- lista fija en codigo, no en base de datos: agregar/quitar un
# modulo es un cambio de producto, no algo que deba ser configurable en
# runtime. module_key debe coincidir con lo que el frontend de cada
# clinica use para identificar esa seccion.
TENANT_MODULES: list[tuple[str, str]] = [
    ("agenda", "Agenda"),
    ("pacientes", "Pacientes"),
    ("facturacion", "Facturacion"),
    ("operaciones", "Operaciones"),
    ("catalogos", "Catalogos"),
]
TENANT_MODULE_KEYS = {key for key, _label in TENANT_MODULES}

TENANT_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


def _validate_tenant_id(tenant_id: str) -> str:
    value = tenant_id.strip()
    if not value or not TENANT_ID_PATTERN.fullmatch(value):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tenant_id solo puede contener letras minusculas, numeros y guiones bajos.",
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="DATABASE_URL no esta configurada.")
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
            detail=f"No se encontro el archivo de esquema: {schema_file}",
        )

    tenant_engine = create_engine(_tenant_database_url(db_name), pool_pre_ping=True)
    try:
        schema_sql = schema_file.read_text(encoding="utf-8")
        with tenant_engine.begin() as connection:
            for statement in _iter_sql_statements(schema_sql):
                connection.execute(text(statement))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo la ejecucion del esquema: {exc}") from exc
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
                    detail=f"La base de datos '{db_name}' ya existe.",
                )
            connection.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}`"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo la creacion de la base de datos: {exc}") from exc
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
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Correo duplicado en la solicitud de aprovisionamiento.")

        existing = db.query(User).filter(User.email.in_(all_emails), User.deleted_at.is_(None)).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El usuario '{existing.email}' ya existe en la base de datos '{db_name}'.",
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo la creacion del usuario: {exc}") from exc
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo el aprovisionamiento de la clinica: {exc}") from exc

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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo el listado de clinicas: {exc}") from exc
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
                            "billing_contact_name": tenant.billing_contact_name,
                            "billing_contact_phone": tenant.billing_contact_phone,
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


def update_tenant(
    tenant_id: str,
    name: str | None,
    status: TenantStatus | None,
    billing_contact_name: str | None = None,
    billing_contact_phone: str | None = None,
) -> dict:
    safe_tenant_id = _validate_tenant_id(tenant_id)
    db_name = _database_name(safe_tenant_id)

    admin_engine = create_engine(_server_database_url(), pool_pre_ping=True)
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(text("SHOW DATABASES LIKE :db_name"), {"db_name": db_name}).scalar()
    finally:
        admin_engine.dispose()
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinica no encontrada.")

    tenant_engine = create_engine(_tenant_database_url(db_name), pool_pre_ping=True)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = session_factory()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == safe_tenant_id).first()
        if tenant is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinica no encontrada.")
        if name is not None:
            tenant.name = name.strip()
        if status is not None:
            tenant.status = status
            # No se toca sessions_invalidated_at aca: get_current_user() ya
            # revisa Tenant.status en cada request (H-09) y corta el acceso
            # de inmediato con 403 "clinic has been deactivated", sin
            # esperar a que expire el access token. Poner ademas
            # sessions_invalidated_at aqui hacia que get_db() rechazara la
            # request con 401 ANTES de que ese chequeo de status corriera
            # (get_current_user depende de get_db), rompiendo el contrato
            # de codigo de estado que ya prueba
            # test_h09_tenant_deactivation.py. "Cerrar sesiones" sigue
            # disponible como accion explicita aparte via
            # force_tenant_logout().
        if billing_contact_name is not None:
            tenant.billing_contact_name = billing_contact_name.strip() or None
        if billing_contact_phone is not None:
            tenant.billing_contact_phone = billing_contact_phone.strip() or None
        db.commit()
        db.refresh(tenant)
        return {
            "tenant_id": tenant.id,
            "name": tenant.name,
            "country": tenant.country,
            "status": tenant.status,
            "created_at": tenant.created_at,
            "billing_contact_name": tenant.billing_contact_name,
            "billing_contact_phone": tenant.billing_contact_phone,
        }
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo la actualizacion de la clinica: {exc}") from exc
    finally:
        db.close()
        tenant_engine.dispose()


def get_tenant_billing_info(tenant_id: str) -> dict:
    """Datos minimos de una clinica para imprimir en su factura PDF (ver
    app/services/invoice_pdf_service.py) -- nombre y contacto de
    facturacion, sin abrir una sesion de larga vida como update_tenant."""
    safe_tenant_id, tenant_engine = _tenant_engine_or_404(tenant_id)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = session_factory()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == safe_tenant_id).first()
        if tenant is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinica no encontrada.")
        return {
            "tenant_id": tenant.id,
            "name": tenant.name,
            "billing_contact_name": tenant.billing_contact_name,
            "billing_contact_phone": tenant.billing_contact_phone,
        }
    finally:
        db.close()
        tenant_engine.dispose()


def force_tenant_logout(tenant_id: str) -> None:
    """Corta de inmediato TODAS las sesiones activas de una clinica (access y
    refresh tokens ya emitidos), sin cambiar su status. Util para casos
    distintos a bloquear por impago -- ej. sospecha de credenciales
    comprometidas -- donde se quiere forzar un logout sin suspender el
    servicio."""
    safe_tenant_id, tenant_engine = _tenant_engine_or_404(tenant_id)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = session_factory()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == safe_tenant_id).first()
        if tenant is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinica no encontrada.")
        tenant.sessions_invalidated_at = datetime.now(timezone.utc)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo el cierre de sesion forzado: {exc}") from exc
    finally:
        db.close()
        tenant_engine.dispose()


def tenant_technical_stats() -> list[dict]:
    """Distinto de tenant_dashboard_stats(): eso es "que hacen las clinicas"
    (negocio/clinico -- pacientes, citas, facturacion). Esto es "cuanto pesan
    en la base de datos" (tecnico/infraestructura -- tamano en disco,
    cantidad de tablas, filas aproximadas) por clinica, util para
    capacity planning, no para operacion clinica. Una sola consulta a
    information_schema.tables agrupada por schema, no fan-out por tenant
    (mas barato que abrir 12 conexiones -- information_schema ve todas las
    bases del servidor desde una sola conexion admin)."""
    admin_engine = create_engine(_server_database_url(), pool_pre_ping=True)
    try:
        with admin_engine.connect() as connection:
            rows = connection.execute(text("SHOW DATABASES LIKE 'salvio\\_%'")).fetchall()
            db_names = [row[0] for row in rows if row[0] not in _RESERVED_DB_NAMES]
            if not db_names:
                return []

            stmt = text(
                """
                SELECT table_schema AS db_name,
                       COUNT(*) AS table_count,
                       COALESCE(SUM(data_length + index_length), 0) AS size_bytes,
                       COALESCE(SUM(table_rows), 0) AS approx_rows,
                       MAX(update_time) AS last_updated
                FROM information_schema.tables
                WHERE table_schema IN :db_names
                GROUP BY table_schema
                """
            ).bindparams(bindparam("db_names", expanding=True))
            stats_rows = connection.execute(stmt, {"db_names": db_names}).fetchall()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo la consulta de metricas tecnicas: {exc}") from exc
    finally:
        admin_engine.dispose()

    by_db_name = {row.db_name: row for row in stats_rows}
    results: list[dict] = []
    for db_name in db_names:
        tenant_id = db_name.removeprefix("salvio_")
        row = by_db_name.get(db_name)
        results.append(
            {
                "tenant_id": tenant_id,
                "table_count": int(row.table_count) if row else 0,
                "size_mb": round((row.size_bytes or 0) / (1024 * 1024), 2) if row else 0.0,
                "approx_rows": int(row.approx_rows) if row and row.approx_rows is not None else 0,
                "last_updated": row.last_updated if row else None,
            }
        )
    results.sort(key=lambda t: t["tenant_id"])
    return results


def tenant_table_breakdown(tenant_id: str) -> list[dict]:
    """Detalle por-tabla de UNA clinica (a diferencia de
    tenant_technical_stats(), que agrega por clinica) -- insumo para armar
    paquetes/tiers de facturacion segun cuanto pesa cada tabla, no solo el
    total."""
    safe_tenant_id = _validate_tenant_id(tenant_id)
    db_name = _database_name(safe_tenant_id)

    admin_engine = create_engine(_server_database_url(), pool_pre_ping=True)
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(text("SHOW DATABASES LIKE :db_name"), {"db_name": db_name}).scalar()
            if not exists:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinica no encontrada.")

            rows = connection.execute(
                text(
                    """
                    SELECT table_name AS table_name,
                           COALESCE(table_rows, 0) AS approx_rows,
                           COALESCE(data_length + index_length, 0) AS size_bytes,
                           update_time AS last_updated
                    FROM information_schema.tables
                    WHERE table_schema = :db_name
                    ORDER BY (data_length + index_length) DESC
                    """
                ),
                {"db_name": db_name},
            ).fetchall()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo la consulta de desglose por tabla: {exc}") from exc
    finally:
        admin_engine.dispose()

    return [
        {
            "table_name": row.table_name,
            "approx_rows": int(row.approx_rows),
            "size_mb": round(row.size_bytes / (1024 * 1024), 3),
            "last_updated": row.last_updated,
        }
        for row in rows
    ]


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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo la agregacion del dashboard: {exc}") from exc
    finally:
        admin_engine.dispose()

    tenants: list[dict] = []
    totals = {
        "patients": 0,
        "appointments": 0,
        "encounters": 0,
        "billing_pending": 0.0,
        "billing_paid": 0.0,
        "staff": 0,
        "prescriptions": 0,
        "lab_orders": 0,
        "appointments_completed": 0,
        "appointments_cancelled": 0,
    }

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

                # Quien realmente esta usando la clinica (headcount + ultima
                # actividad), no solo cuanto contenido clinico acumulo.
                staff_count = db.query(func.count(User.id)).filter(User.tenant_id == tenant_id, User.is_active.is_(True), User.deleted_at.is_(None)).scalar() or 0
                last_activity_at = db.query(func.max(User.last_login_at)).filter(User.tenant_id == tenant_id).scalar()

                # "Que hacen las clinicas" mas alla de citas/pacientes crudos:
                # cuanto se receta, cuanto se manda a laboratorio, y como se
                # resuelven las citas (completadas vs canceladas/no-show).
                prescriptions_count = db.query(func.count(Prescription.id)).filter(Prescription.tenant_id == tenant_id).scalar() or 0
                lab_orders_count = db.query(func.count(LabOrder.id)).filter(LabOrder.tenant_id == tenant_id).scalar() or 0
                appointments_completed = (
                    db.query(func.count(Appointment.id))
                    .filter(Appointment.tenant_id == tenant_id, Appointment.deleted_at.is_(None), Appointment.status == AppointmentStatus.completed)
                    .scalar()
                    or 0
                )
                appointments_cancelled = (
                    db.query(func.count(Appointment.id))
                    .filter(
                        Appointment.tenant_id == tenant_id,
                        Appointment.deleted_at.is_(None),
                        Appointment.status.in_([AppointmentStatus.cancelled, AppointmentStatus.no_show]),
                    )
                    .scalar()
                    or 0
                )

                # Modulos apagados (ver TENANT_MODULES / "Inactivar" en el
                # panel del dueno) -- sin fila = habilitado por defecto.
                disabled_modules = {
                    row.module_key
                    for row in db.query(TenantModuleFlag).filter(TenantModuleFlag.tenant_id == tenant_id, TenantModuleFlag.enabled.is_(False)).all()
                }
                modules_active = len(TENANT_MODULES) - len(disabled_modules)

                entry = {
                    "tenant_id": tenant.id,
                    "name": tenant.name,
                    "status": tenant.status,
                    "patients_count": patients_count,
                    "appointments_count": appointments_count,
                    "encounters_count": encounters_count,
                    "billing_pending": billing_pending,
                    "billing_paid": billing_paid,
                    "staff_count": staff_count,
                    "last_activity_at": last_activity_at,
                    "prescriptions_count": prescriptions_count,
                    "lab_orders_count": lab_orders_count,
                    "appointments_completed": appointments_completed,
                    "appointments_cancelled": appointments_cancelled,
                    "modules_active": modules_active,
                    "modules_total": len(TENANT_MODULES),
                }
                tenants.append(entry)
                totals["patients"] += patients_count
                totals["appointments"] += appointments_count
                totals["encounters"] += encounters_count
                totals["billing_pending"] += billing_pending
                totals["billing_paid"] += billing_paid
                totals["staff"] += staff_count
                totals["prescriptions"] += prescriptions_count
                totals["lab_orders"] += lab_orders_count
                totals["appointments_completed"] += appointments_completed
                totals["appointments_cancelled"] += appointments_cancelled
            finally:
                db.close()
        except SQLAlchemyError:
            continue
        finally:
            tenant_engine.dispose()

    tenants.sort(key=lambda t: t["tenant_id"])
    return {"tenants": tenants, "totals": totals}


def ensure_tenant_exists(tenant_id: str) -> str:
    """Valida formato y confirma que la BD del tenant existe, sin abrir una
    conexion persistente a ella -- para llamadores que solo necesitan
    confirmar existencia (ej. facturacion de plataforma, que vive en
    salvio_control, no en la BD del tenant). Ver _tenant_engine_or_404 para
    el caso que si necesita una conexion a la BD del tenant."""
    safe_tenant_id = _validate_tenant_id(tenant_id)
    db_name = _database_name(safe_tenant_id)
    admin_engine = create_engine(_server_database_url(), pool_pre_ping=True)
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(text("SHOW DATABASES LIKE :db_name"), {"db_name": db_name}).scalar()
    finally:
        admin_engine.dispose()
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinica no encontrada.")
    return safe_tenant_id


def _tenant_engine_or_404(tenant_id: str):
    safe_tenant_id = _validate_tenant_id(tenant_id)
    db_name = _database_name(safe_tenant_id)

    admin_engine = create_engine(_server_database_url(), pool_pre_ping=True)
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(text("SHOW DATABASES LIKE :db_name"), {"db_name": db_name}).scalar()
    finally:
        admin_engine.dispose()
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinica no encontrada.")

    return safe_tenant_id, create_engine(_tenant_database_url(db_name), pool_pre_ping=True)


def list_tenant_modules(tenant_id: str) -> list[dict]:
    safe_tenant_id, tenant_engine = _tenant_engine_or_404(tenant_id)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = session_factory()
    try:
        rows = db.query(TenantModuleFlag).filter(TenantModuleFlag.tenant_id == safe_tenant_id).all()
        enabled_by_key = {row.module_key: row.enabled for row in rows}
        return [
            {"module_key": key, "label": label, "enabled": enabled_by_key.get(key, True)}
            for key, label in TENANT_MODULES
        ]
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo el listado de modulos: {exc}") from exc
    finally:
        db.close()
        tenant_engine.dispose()


def set_tenant_module(tenant_id: str, module_key: str, enabled: bool) -> dict:
    if module_key not in TENANT_MODULE_KEYS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Modulo desconocido '{module_key}'.")

    safe_tenant_id, tenant_engine = _tenant_engine_or_404(tenant_id)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = session_factory()
    try:
        flag = (
            db.query(TenantModuleFlag)
            .filter(TenantModuleFlag.tenant_id == safe_tenant_id, TenantModuleFlag.module_key == module_key)
            .first()
        )
        if flag is None:
            flag = TenantModuleFlag(id=uuid4().bytes, tenant_id=safe_tenant_id, module_key=module_key, enabled=enabled)
            db.add(flag)
        else:
            flag.enabled = enabled
        db.commit()
        label = dict(TENANT_MODULES)[module_key]
        return {"module_key": module_key, "label": label, "enabled": enabled}
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo la actualizacion del modulo: {exc}") from exc
    finally:
        db.close()
        tenant_engine.dispose()


# Roles que el dueno de la plataforma puede gestionar desde el panel
# (crear/editar/eliminar) para una clinica. Deliberadamente excluye
# clinic_admin (se crea solo una vez, al aprovisionar la clinica -- ver
# create_tenant()), super_admin (no existe a nivel de clinica) y patient
# (se gestiona desde el modulo de pacientes de la clinica, no desde aca).
MANAGEABLE_STAFF_ROLES = {
    UserRole.doctor,
    UserRole.resident,
    UserRole.nurse,
    UserRole.receptionist,
    UserRole.accountant,
}


def _validate_staff_role(role_value: str) -> UserRole:
    try:
        role = UserRole(role_value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Rol desconocido '{role_value}'.") from None
    if role not in MANAGEABLE_STAFF_ROLES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"El rol '{role_value}' no se puede administrar desde este panel.")
    return role


def _staff_to_dict(member: User) -> dict:
    return {
        "id": UUID(bytes=member.id),
        "full_name": member.full_name,
        "role": member.role.value if hasattr(member.role, "value") else str(member.role),
        "specialty": member.specialty or "",
        "email": member.email,
        "is_active": member.is_active,
    }


def list_tenant_staff(tenant_id: str, role: str | None = None) -> list[dict]:
    safe_tenant_id, tenant_engine = _tenant_engine_or_404(tenant_id)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = session_factory()
    try:
        query = db.query(User).filter(
            User.tenant_id == safe_tenant_id,
            User.role.in_(MANAGEABLE_STAFF_ROLES),
            User.deleted_at.is_(None),
        )
        if role is not None:
            query = query.filter(User.role == _validate_staff_role(role))
        members = query.order_by(User.full_name).all()
        return [_staff_to_dict(member) for member in members]
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo el listado del equipo: {exc}") from exc
    finally:
        db.close()
        tenant_engine.dispose()


def create_tenant_staff(tenant_id: str, data: dict) -> dict:
    role = _validate_staff_role(data["role"])
    safe_tenant_id, tenant_engine = _tenant_engine_or_404(tenant_id)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = session_factory()
    try:
        email = data["email"].strip().lower()
        existing = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"El usuario '{email}' ya existe.")

        new_member = User(
            id=uuid4().bytes,
            tenant_id=safe_tenant_id,
            email=email,
            hashed_password=pwd_context.hash(normalize_password(data["password"])),
            full_name=data["full_name"].strip(),
            role=role,
            specialty=(data.get("specialty") or "").strip() or None,
            is_active=True,
        )
        db.add(new_member)
        db.commit()
        db.refresh(new_member)
        return _staff_to_dict(new_member)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo la creacion del miembro del equipo: {exc}") from exc
    finally:
        db.close()
        tenant_engine.dispose()


def _get_staff_member(db: Session, safe_tenant_id: str, user_id: str) -> User:
    try:
        user_uuid = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Id de usuario invalido.") from exc

    member = (
        db.query(User)
        .filter(
            User.id == user_uuid.bytes,
            User.tenant_id == safe_tenant_id,
            User.role.in_(MANAGEABLE_STAFF_ROLES),
            User.deleted_at.is_(None),
        )
        .first()
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miembro del equipo no encontrado.")
    return member


def update_tenant_staff(tenant_id: str, user_id: str, data: dict) -> dict:
    safe_tenant_id, tenant_engine = _tenant_engine_or_404(tenant_id)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = session_factory()
    try:
        member = _get_staff_member(db, safe_tenant_id, user_id)

        if data.get("full_name") is not None:
            member.full_name = data["full_name"].strip()
        if data.get("specialty") is not None:
            member.specialty = data["specialty"].strip() or None
        if data.get("email") is not None:
            new_email = data["email"].strip().lower()
            if new_email != member.email:
                existing = db.query(User).filter(User.email == new_email, User.deleted_at.is_(None)).first()
                if existing:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"El usuario '{new_email}' ya existe.")
                member.email = new_email
        if data.get("is_active") is not None:
            member.is_active = data["is_active"]

        db.commit()
        db.refresh(member)
        return _staff_to_dict(member)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo la actualizacion del miembro del equipo: {exc}") from exc
    finally:
        db.close()
        tenant_engine.dispose()


def delete_tenant_staff(tenant_id: str, user_id: str) -> None:
    safe_tenant_id, tenant_engine = _tenant_engine_or_404(tenant_id)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = session_factory()
    try:
        member = _get_staff_member(db, safe_tenant_id, user_id)
        member.is_active = False
        member.deleted_at = datetime.now(timezone.utc)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo la desactivacion del miembro del equipo: {exc}") from exc
    finally:
        db.close()
        tenant_engine.dispose()


def _get_admin_member(db: Session, safe_tenant_id: str) -> User:
    """Analogo a _get_staff_member, pero para la cuenta clinic_admin -- que
    _get_staff_member excluye a proposito via MANAGEABLE_STAFF_ROLES (ver
    comentario en esa constante). Solo existe una por clinica, creada al
    aprovisionar (create_tenant), asi que no hace falta un user_id: el
    dueno pide "el admin de esta clinica", no un id especifico."""
    member = (
        db.query(User)
        .filter(User.tenant_id == safe_tenant_id, User.role == UserRole.clinic_admin, User.deleted_at.is_(None))
        .first()
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Administrador de clinica no encontrado.")
    return member


def get_tenant_admin(tenant_id: str) -> dict:
    safe_tenant_id, tenant_engine = _tenant_engine_or_404(tenant_id)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = session_factory()
    try:
        member = _get_admin_member(db, safe_tenant_id)
        return _staff_to_dict(member)
    finally:
        db.close()
        tenant_engine.dispose()


def reset_tenant_admin_password(tenant_id: str) -> dict:
    """Mismo proposito que reset_tenant_staff_password, para clinic_admin.
    Deliberadamente SIN opcion de eliminar/desactivar al admin desde aca --
    una clinica solo tiene uno, y borrarlo la dejaria sin nadie con ese rol
    (a diferencia del resto del equipo, que se puede recrear libremente)."""
    safe_tenant_id, tenant_engine = _tenant_engine_or_404(tenant_id)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = session_factory()
    try:
        member = _get_admin_member(db, safe_tenant_id)
        new_password = _generate_temp_password()
        member.hashed_password = pwd_context.hash(normalize_password(new_password))
        db.commit()
        return {"id": UUID(bytes=member.id), "email": member.email, "new_password": new_password}
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo el restablecimiento de contrasena: {exc}") from exc
    finally:
        db.close()
        tenant_engine.dispose()


def force_tenant_admin_logout(tenant_id: str) -> None:
    safe_tenant_id, tenant_engine = _tenant_engine_or_404(tenant_id)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = session_factory()
    try:
        member = _get_admin_member(db, safe_tenant_id)
        member.sessions_invalidated_at = datetime.now(timezone.utc)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo el cierre de sesion forzado: {exc}") from exc
    finally:
        db.close()
        tenant_engine.dispose()


def _generate_temp_password(length: int = 12) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def reset_tenant_staff_password(tenant_id: str, user_id: str) -> dict:
    """Reset forzado desde el panel del dueno -- para cuando un miembro del
    equipo perdio acceso a su cuenta y no hay flujo de "olvide mi
    contrasena" disponible para el (o el dueno necesita revocar
    credenciales de inmediato). Genera una contrasena temporal nueva y la
    devuelve en texto plano UNA sola vez en la respuesta -- nunca se vuelve
    a poder consultar despues de esto, igual que las contrasenas generadas
    al crear un miembro nuevo."""
    safe_tenant_id, tenant_engine = _tenant_engine_or_404(tenant_id)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = session_factory()
    try:
        member = _get_staff_member(db, safe_tenant_id, user_id)
        new_password = _generate_temp_password()
        member.hashed_password = pwd_context.hash(normalize_password(new_password))
        db.commit()
        return {"id": UUID(bytes=member.id), "email": member.email, "new_password": new_password}
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo el restablecimiento de contrasena: {exc}") from exc
    finally:
        db.close()
        tenant_engine.dispose()


def force_staff_logout(tenant_id: str, user_id: str) -> None:
    """Cierra sesion de UNA sola persona del equipo (distinto de
    force_tenant_logout, que corta a toda la clinica de una vez)."""
    safe_tenant_id, tenant_engine = _tenant_engine_or_404(tenant_id)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = session_factory()
    try:
        member = _get_staff_member(db, safe_tenant_id, user_id)
        member.sessions_invalidated_at = datetime.now(timezone.utc)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fallo el cierre de sesion forzado: {exc}") from exc
    finally:
        db.close()
        tenant_engine.dispose()


def tenant_login_activity(tenant_id: str, days: int = 30) -> list[dict]:
    """IPs distintas que iniciaron sesion en esta clinica en los ultimos
    `days` dias, para que el owner pueda ver quien esta accediendo. Se arma
    en Python (no GROUP_CONCAT en SQL) para no depender de configuracion de
    MySQL group_concat_max_len."""
    safe_tenant_id, tenant_engine = _tenant_engine_or_404(tenant_id)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    db: Session = session_factory()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.query(AuditLog.ip_address, AuditLog.user_id, AuditLog.created_at)
            .filter(
                AuditLog.tenant_id == safe_tenant_id,
                AuditLog.action == "LOGIN",
                AuditLog.created_at >= cutoff,
                AuditLog.ip_address.isnot(None),
            )
            .all()
        )
        user_ids = {row.user_id for row in rows if row.user_id is not None}
        emails_by_id = {}
        if user_ids:
            for user in db.query(User.id, User.email).filter(User.id.in_(user_ids)).all():
                emails_by_id[user.id] = user.email

        by_ip: dict[str, dict] = {}
        for row in rows:
            entry = by_ip.setdefault(row.ip_address, {"ip_address": row.ip_address, "login_count": 0, "last_seen": row.created_at, "users": set()})
            entry["login_count"] += 1
            if row.created_at > entry["last_seen"]:
                entry["last_seen"] = row.created_at
            email = emails_by_id.get(row.user_id)
            if email:
                entry["users"].add(email)

        results = [{**entry, "users": sorted(entry["users"])} for entry in by_ip.values()]
        results.sort(key=lambda e: e["last_seen"], reverse=True)
        return results
    finally:
        db.close()
        tenant_engine.dispose()
