from sqlalchemy import Column, Date, ForeignKey, Index, SmallInteger, String, Text, Time
from sqlalchemy.dialects.mysql import BINARY
from sqlalchemy.sql import func
from sqlalchemy import DateTime

from app.database import Base


class DoctorWeeklyHours(Base):
    """Horario recurrente semanal de un medico (full-time/part-time). Sin
    ninguna fila para un medico = sin restriccion (disponible siempre, igual
    que hoy) -- es un modelo opt-in, no rompe medicos existentes que nunca
    configuraron horario. day_of_week: 0=lunes .. 6=domingo (ISO)."""
    __tablename__ = "doctor_weekly_hours"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    doctor_id = Column(BINARY(16), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(SmallInteger, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_doctor_weekly_hours_doctor", "tenant_id", "doctor_id", "day_of_week"),
    )


class DoctorAbsence(Base):
    """Ausencia de un medico en un rango de fechas (viaje, incapacidad,
    etc.) -- bloquea agenda completa en ese rango, distinto del horario
    recurrente semanal."""
    __tablename__ = "doctor_absences"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    doctor_id = Column(BINARY(16), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_doctor_absences_doctor", "tenant_id", "doctor_id", "start_date", "end_date"),
    )
