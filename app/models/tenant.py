from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum, ForeignKey, Index, SmallInteger, Text
from sqlalchemy.dialects.mysql import BINARY
from sqlalchemy.sql import func
from app.database import Base
import enum

class TenantStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    archived = "archived"

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False)
    country = Column(String(2), nullable=False, default="SV")
    status = Column(SQLEnum(TenantStatus), nullable=False, default=TenantStatus.active)
    # Distinto de `status`: bloquear una clinica detiene logins NUEVOS pero un
    # access token ya emitido seguia siendo valido hasta su expiracion natural
    # (hasta 60 min por default). Este timestamp permite cortar sesiones YA
    # activas de inmediato -- cualquier token con "iat" anterior a este valor
    # se rechaza en get_db()/refresh_token, sin importar si sigue sin expirar.
    sessions_invalidated_at = Column(DateTime, nullable=True)
    # Contacto de facturacion de la clinica (a quien va dirigida la factura
    # PDF que genera el dueno desde Facturacion -- ver PlatformCharge). No es
    # necesariamente el clinic_admin: puede ser el dueno/administrador del
    # negocio, que no siempre tiene cuenta de usuario en el sistema.
    billing_contact_name = Column(String(255), nullable=True)
    billing_contact_phone = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

class TenantModuleFlag(Base):
    """Interruptor por modulo dentro de una clinica (distinto de
    Tenant.status: bloquear apaga TODO el acceso, esto apaga solo un modulo
    especifico -- ej. el cliente dejo de contratar Facturacion pero sigue
    usando Agenda). No hay fila = modulo habilitado por defecto."""
    __tablename__ = "tenant_module_flags"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    module_key = Column(String(50), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        Index("uq_tenant_module", "tenant_id", "module_key", unique=True),
    )

class UserRole(str, enum.Enum):
    super_admin = "super_admin"
    clinic_admin = "clinic_admin"
    doctor = "doctor"
    resident = "resident"
    nurse = "nurse"
    receptionist = "receptionist"
    accountant = "accountant"
    patient = "patient"

class BedStatus(str, enum.Enum):
    available = "available"
    occupied = "occupied"
    cleaning = "cleaning"
    maintenance = "maintenance"
    blocked = "blocked"

class User(Base):
    __tablename__ = "users"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    specialty = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    deleted_at = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    # Analogo a Tenant.sessions_invalidated_at pero para UN usuario -- permite
    # "cerrar sesion" de una sola persona del equipo sin afectar al resto de
    # la clinica (distinto de force_tenant_logout, que es clinica completa).
    sessions_invalidated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        Index("idx_users_tenant", "tenant_id"),
        Index("idx_users_tenant_role", "tenant_id", "role"),
        Index("idx_users_deleted", "deleted_at"),
    )

class RevokedToken(Base):
    __tablename__ = "revoked_tokens"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    jti = Column(String(255), nullable=False, unique=True)
    user_id = Column(BINARY(16), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    __table_args__ = (Index("idx_revtok_exp", "expires_at"),)

class OtpTokenSms(Base):
    __tablename__ = "otp_tokens_sms"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    user_id = Column(BINARY(16), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    phone_number = Column(String(30), nullable=False)
    otp_code_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    __table_args__ = (
        Index("idx_otp_user", "user_id"),
        Index("idx_otp_expires", "expires_at"),
    )

class HcTemplate(Base):
    __tablename__ = "hc_templates"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    specialty = Column(String(100), nullable=False)
    require_insurance_affiliation = Column(Boolean, nullable=False, default=False)
    require_labor_data = Column(Boolean, nullable=False, default=False)
    require_attention_number = Column(Boolean, nullable=False, default=False)
    show_glasgow_scale = Column(Boolean, nullable=False, default=False)
    show_triage = Column(Boolean, nullable=False, default=False)
    show_pediatric_perinatal = Column(Boolean, nullable=False, default=False)
    show_clinical_scales = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    __table_args__ = (Index("uq_hctpl_tenant_specialty", "tenant_id", "specialty", unique=True),)

class Facility(Base):
    __tablename__ = "facilities"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    facility_type = Column(String(100), nullable=True)
    phone = Column(String(30), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_facilities_tenant", "tenant_id"),
        Index("uq_facilities_tenant_name", "tenant_id", "name", unique=True),
    )

class Department(Base):
    __tablename__ = "departments"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    facility_id = Column(BINARY(16), ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    specialty = Column(String(100), nullable=True)
    is_clinical = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_departments_tenant", "tenant_id"),
        Index("idx_departments_facility", "facility_id"),
        Index("uq_departments_tenant_name", "tenant_id", "name", unique=True),
    )

class Room(Base):
    __tablename__ = "rooms"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    facility_id = Column(BINARY(16), ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True)
    department_id = Column(BINARY(16), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    room_number = Column(String(50), nullable=False)
    room_type = Column(String(100), nullable=True)
    floor = Column(String(50), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_rooms_tenant", "tenant_id"),
        Index("idx_rooms_department", "department_id"),
        Index("uq_rooms_tenant_number", "tenant_id", "room_number", unique=True),
    )

class Bed(Base):
    __tablename__ = "beds"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    room_id = Column(BINARY(16), ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    bed_number = Column(String(50), nullable=False)
    status = Column(SQLEnum(BedStatus), nullable=False, default="available")
    current_admission_id = Column(BINARY(16), ForeignKey("patient_admissions.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_beds_tenant", "tenant_id"),
        Index("idx_beds_room", "room_id"),
        Index("idx_beds_status", "tenant_id", "status"),
        Index("uq_beds_tenant_number", "tenant_id", "bed_number", unique=True),
    )
