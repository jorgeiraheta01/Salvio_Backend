from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum, Text, Index, Numeric
from sqlalchemy.dialects.mysql import BINARY, TINYINT, SET
from sqlalchemy.sql import func
from app.database import Base
import enum

class MilestoneCategory(str, enum.Enum):
    motor_gross = "motor_gross"
    motor_fine = "motor_fine"
    communication_language = "communication_language"
    cognitive = "cognitive"
    social_emotional = "social_emotional"

class DevelopmentMilestoneConfig(Base):
    __tablename__ = "development_milestones_config"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    milestone_name = Column(String(255), nullable=False)
    category = Column(SQLEnum(MilestoneCategory), nullable=False)
    age_median_months = Column(Numeric(5,1), nullable=False)
    alert_age_months = Column(Numeric(5,1), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    __table_args__ = (Index("idx_milestones_category", "category"),)

class ClinicalSystemCatalog(Base):
    __tablename__ = "clinical_systems_catalog"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    system_name = Column(String(100), nullable=False, unique=True)
    applies_to = Column(SET('exam', 'review'), nullable=False, default="exam,review")
    sort_order = Column(TINYINT, nullable=False, default=0)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

class Cie10Catalog(Base):
    """Catalogo compartido de codigos CIE-10 (global, sin tenant_id --
    mismo patron que ClinicalSystemCatalog/LabTestCatalog, ver H-07 en
    catalog_service.py). Sembrado inicial con un set reducido de codigos
    de alta confianza (ver scripts/seed_cie10.py); se amplia con el tiempo
    vía el mismo CRUD, no se importa el CIE-10 completo de una vez."""
    __tablename__ = "cie10_catalog"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    code = Column(String(10), nullable=False, unique=True)
    description = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    __table_args__ = (Index("idx_cie10_description", "description"),)

class LabTestCatalog(Base):
    __tablename__ = "lab_tests_catalog"
    id = Column(BINARY(16), primary_key=True, server_default="UUID_TO_BIN(UUID())")
    test_code = Column(String(20), nullable=False, unique=True)
    test_name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    unit = Column(String(50), nullable=True)
    ref_range = Column(String(100), nullable=True)
    sample_type = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())