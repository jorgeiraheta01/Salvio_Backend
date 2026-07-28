from sqlalchemy import BINARY, Column, DateTime, JSON, String, Text
from sqlalchemy.sql import func

from app.models.platform_admin import ControlBase


class ControlAuditLog(ControlBase):
    """Bitacora de acciones del owner de la plataforma, en salvio_control.

    Deliberadamente separada del AuditLog de tenant (app/models/audit.py):
    ese vive en cada BD de clinica y su actor es un User de esa clinica;
    esta vive una sola vez en salvio_control y su actor es siempre un
    PlatformAdmin, sin importar sobre que tenant haya actuado.
    """

    __tablename__ = "audit_log"

    id = Column(BINARY(16), primary_key=True)
    admin_id = Column(BINARY(16), nullable=True)
    tenant_id = Column(String(50), nullable=True)
    action = Column(String(50), nullable=False)
    table_name = Column(String(100), nullable=False)
    record_id = Column(BINARY(16), nullable=True)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
