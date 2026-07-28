from sqlalchemy import BINARY, Boolean, Column, DateTime, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

# Deliberately its own declarative base, separate from the per-tenant Base in
# app/database.py — platform_admins lives in a single control-plane database
# (salvio_control), never in a tenant's own salvio_<tenant_id> database.
# Tenants are clinics (ADR-01); the platform owner is not a clinic.
ControlBase = declarative_base()


class PlatformAdmin(ControlBase):
    __tablename__ = "platform_admins"

    id = Column(BINARY(16), primary_key=True)
    email = Column(String(255), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class ControlRevokedToken(ControlBase):
    """Tokens de platform_admin revocados por logout.

    Antes de esto no existia forma de cerrar la sesion de un owner: los
    tokens de 8h eran validos hasta que expiraban por su cuenta, sin
    posibilidad de cortarlos antes (ej. si el dispositivo se perdio).
    """

    __tablename__ = "revoked_tokens"

    id = Column(BINARY(16), primary_key=True)
    jti = Column(String(255), nullable=False, unique=True)
    admin_id = Column(BINARY(16), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
