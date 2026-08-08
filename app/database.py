import os
from datetime import timezone
from uuid import UUID
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY") or "salvio-dev-secret-change-me"
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

_tenant_bearer = HTTPBearer(auto_error=False)
_tenant_engines: dict[str, Engine] = {}
_control_engine: Engine | None = None

CONTROL_DB_NAME = "salvio_control"


def tenant_db_name(tenant_id: str) -> str:
    return f"salvio_{tenant_id}"


def get_control_engine() -> Engine:
    """Returns a cached engine bound to the platform control-plane database
    (salvio_control) — home of platform_admins, the identity used to provision
    new clinics. Deliberately NOT a tenant: tenants are clinics (ADR-01);
    the platform owner is not one."""
    global _control_engine
    if _control_engine is None:
        url = make_url(DATABASE_URL).set(database=CONTROL_DB_NAME).render_as_string(hide_password=False)
        _control_engine = create_engine(url, pool_pre_ping=True)
    return _control_engine


def get_tenant_engine(tenant_id: str) -> Engine:
    """Returns a cached SQLAlchemy engine bound to the given tenant's own database
    (database-per-tenant isolation, ADR-01). Engines are created once per tenant_id
    and reused for the lifetime of the process instead of being opened/disposed per
    request."""
    if tenant_id not in _tenant_engines:
        url = make_url(DATABASE_URL).set(database=tenant_db_name(tenant_id)).render_as_string(hide_password=False)
        _tenant_engines[tenant_id] = create_engine(url, pool_pre_ping=True)
    return _tenant_engines[tenant_id]


def _cutoff_rejects(issued_at: int | None, invalidated_at) -> bool:
    if invalidated_at is None:
        return False
    cutoff = invalidated_at.replace(tzinfo=timezone.utc).timestamp()
    return issued_at is None or issued_at < cutoff


def _reject_if_session_invalidated(db: Session, tenant_id: str, payload: dict) -> None:
    """Comparte el chequeo de force-logout entre get_db() y /auth/refresh.
    Dos niveles independientes: clinica completa (Tenant.sessions_invalidated_at,
    "Cerrar sesiones" a nivel tenant) y una sola persona
    (User.sessions_invalidated_at, "Cerrar sesion" de un miembro del equipo).
    Import diferido de Tenant/User para evitar el ciclo app.database <->
    app.models.tenant (models/tenant.py hace `from app.database import Base`)."""
    from app.models.tenant import Tenant, User

    issued_at = payload.get("iat")

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is not None and _cutoff_rejects(issued_at, tenant.sessions_invalidated_at):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesion revocada. Inicia sesion de nuevo.")

    user_id = payload.get("sub")
    if user_id:
        try:
            user_bytes = UUID(user_id).bytes
        except ValueError:
            return
        user = db.query(User).filter(User.id == user_bytes, User.tenant_id == tenant_id).first()
        if user is not None and _cutoff_rejects(issued_at, user.sessions_invalidated_at):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesion revocada. Inicia sesion de nuevo.")


def get_db(credentials: HTTPAuthorizationCredentials | None = Depends(_tenant_bearer)):
    """Tenant-aware DB session dependency. Resolves the target database from the
    tenant_id claim of the caller's JWT (the same source of truth used at login),
    never from a client-suppliable header, so a request always lands in its own
    tenant's database and can never be pointed at another tenant's data."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado.")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido o expirado.") from None

    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido.")

    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_tenant_engine(tenant_id))
    db: Session = session_factory()
    try:
        _reject_if_session_invalidated(db, tenant_id, payload)
        yield db
    finally:
        db.close()
