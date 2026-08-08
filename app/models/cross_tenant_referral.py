from sqlalchemy import Column, Date, DateTime, Index, String, Text
from sqlalchemy.dialects.mysql import BINARY
from sqlalchemy.sql import func

from app.models.platform_admin import ControlBase


class CrossTenantReferralIndex(ControlBase):
    """Espejo minimo, en el plano de control, de las referencias cross_tenant.

    Los `Referral` viven unicamente en la base del tenant que los crea
    (aislamiento por tenant, ADR-01) -- el tenant destino no tiene acceso a
    esa base de datos. Sin este indice, el tenant destino no tiene forma de
    descubrir que se le referio un paciente. Guarda solo lo necesario para
    listar referencias entrantes; el detalle clinico se lee en vivo desde el
    tenant de origen via get_tenant_engine (ver /referrals/cross-tenant/*)."""

    __tablename__ = "cross_tenant_referral_index"

    id = Column(BINARY(16), primary_key=True)
    referral_id = Column(BINARY(16), nullable=False, unique=True)
    source_tenant_id = Column(String(50), nullable=False)
    target_tenant_id = Column(String(50), nullable=False)
    patient_id = Column(BINARY(16), nullable=False)
    patient_name = Column(String(255), nullable=False)
    # Copia minima de contacto/identidad del paciente -- el tenant destino no
    # tiene acceso a la base de origen para leerlos, y los necesita para
    # poder agendarle una cita (telefono) sin tener que pedirselos de nuevo.
    patient_phone = Column(String(30), nullable=True)
    patient_dob = Column(Date, nullable=True)
    patient_gender = Column(String(20), nullable=True)
    patient_dui = Column(String(10), nullable=True)
    patient_nit = Column(String(20), nullable=True)
    patient_email = Column(String(255), nullable=True)
    patient_address = Column(Text, nullable=True)
    patient_emergency_contact_name = Column(String(255), nullable=True)
    patient_emergency_contact_phone = Column(String(30), nullable=True)
    patient_emergency_contact_relationship = Column(String(100), nullable=True)
    patient_insurance_type = Column(String(30), nullable=True)
    patient_insurance_number = Column(String(50), nullable=True)
    referred_by_name = Column(String(255), nullable=True)
    referred_by_specialty = Column(String(255), nullable=True)
    source_tenant_name = Column(String(255), nullable=True)
    target_doctor_id = Column(BINARY(16), nullable=True)
    target_doctor_name = Column(String(255), nullable=True)
    destination_area = Column(String(100), nullable=True)
    transfer_reason = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    # Id del paciente ya creado en la base del tenant destino (una vez que
    # alguien ahi agenda la primera cita) -- evita crear un duplicado si se
    # agenda mas de una vez desde la misma referencia.
    imported_patient_id = Column(BINARY(16), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_ctri_target", "target_tenant_id"),
        Index("idx_ctri_source", "source_tenant_id"),
    )
