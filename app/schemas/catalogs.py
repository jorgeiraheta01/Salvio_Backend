from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import ORMModel, StrippedStringMixin


class MedicationCatalogBase(StrippedStringMixin, ORMModel):
    medication_code: str | None = Field(default=None, max_length=50)
    generic_name: str = Field(min_length=1, max_length=255)
    brand_name: str | None = Field(default=None, max_length=255)
    concentration: str | None = Field(default=None, max_length=100)
    pharmaceutical_form: str | None = Field(default=None, max_length=100)
    route: str | None = Field(default=None, max_length=100)
    is_controlled: bool = False
    is_active: bool = True


class MedicationCatalogCreate(MedicationCatalogBase):
    pass


class MedicationCatalogUpdate(StrippedStringMixin, ORMModel):
    medication_code: str | None = Field(default=None, max_length=50)
    generic_name: str | None = Field(default=None, min_length=1, max_length=255)
    brand_name: str | None = Field(default=None, max_length=255)
    concentration: str | None = Field(default=None, max_length=100)
    pharmaceutical_form: str | None = Field(default=None, max_length=100)
    route: str | None = Field(default=None, max_length=100)
    is_controlled: bool | None = None
    is_active: bool | None = None


class MedicationCatalogRead(MedicationCatalogBase):
    id: UUID
    created_at: datetime


class Cie10CatalogBase(StrippedStringMixin, ORMModel):
    code: str = Field(min_length=1, max_length=10)
    description: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    is_active: bool = True


class Cie10CatalogCreate(Cie10CatalogBase):
    pass


class Cie10CatalogUpdate(StrippedStringMixin, ORMModel):
    description: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class Cie10CatalogRead(Cie10CatalogBase):
    id: UUID
    created_at: datetime


class LabTestCatalogBase(StrippedStringMixin, ORMModel):
    test_code: str = Field(min_length=1, max_length=20)
    test_name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=50)
    ref_range: str | None = Field(default=None, max_length=100)
    sample_type: str | None = Field(default=None, max_length=100)
    is_active: bool = True


class LabTestCatalogCreate(LabTestCatalogBase):
    pass


class LabTestCatalogUpdate(StrippedStringMixin, ORMModel):
    test_code: str | None = Field(default=None, min_length=1, max_length=20)
    test_name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=50)
    ref_range: str | None = Field(default=None, max_length=100)
    sample_type: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class LabTestCatalogRead(LabTestCatalogBase):
    id: UUID
    created_at: datetime


class ClinicalSystemCatalogBase(StrippedStringMixin, ORMModel):
    system_name: str = Field(min_length=1, max_length=100)
    applies_to: str = Field(default="exam,review", max_length=20)
    sort_order: int = 0
    description: str | None = None
    is_active: bool = True


class ClinicalSystemCatalogCreate(ClinicalSystemCatalogBase):
    pass


class ClinicalSystemCatalogUpdate(StrippedStringMixin, ORMModel):
    system_name: str | None = Field(default=None, min_length=1, max_length=100)
    applies_to: str | None = Field(default=None, max_length=20)
    sort_order: int | None = None
    description: str | None = None
    is_active: bool | None = None


class ClinicalSystemCatalogRead(StrippedStringMixin, ORMModel):
    # applies_to viene de una columna SET de MySQL -- SQLAlchemy la lee como
    # un set[str] de Python, no como el string que se manda al crear/editar.
    id: UUID
    system_name: str
    applies_to: set[str]
    sort_order: int
    description: str | None = None
    is_active: bool
    created_at: datetime
