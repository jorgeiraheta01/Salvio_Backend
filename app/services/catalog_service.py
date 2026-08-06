from typing import Any

from sqlalchemy.orm import Session

from app.models.catalogs import Cie10Catalog, ClinicalSystemCatalog, LabTestCatalog
from app.models.inventory import MedicationCatalog
from app.services._utils import audit, commit_or_409, data_for_model, model_to_dict, new_uuid_bytes, not_found

# H-07: los catalogos viven en cada BD de tenant (no en salvio_control) --
# MedicationCatalog admite tenant_id nulo (fila "global", sembrada una vez
# en la plantilla) o un tenant_id especifico; el resto de catalogos no tiene
# columna tenant_id en absoluto porque cada BD de tenant ya es su propio
# espacio de nombres.


def list_medications(db: Session, tenant_id: str) -> list[MedicationCatalog]:
    return db.query(MedicationCatalog).filter((MedicationCatalog.tenant_id == tenant_id) | (MedicationCatalog.tenant_id.is_(None))).order_by(MedicationCatalog.generic_name).all()


def create_medication(db: Session, tenant_id: str, data: Any, user_id: bytes) -> MedicationCatalog:
    payload = data_for_model(data, MedicationCatalog, tenant_id=tenant_id)
    payload["id"] = new_uuid_bytes()
    item = MedicationCatalog(**payload)
    db.add(item)
    db.flush()
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="medication_catalog", record_id=item.id, new_values=model_to_dict(item))
    commit_or_409(db)
    db.refresh(item)
    return item


def update_medication(db: Session, item_id: bytes, tenant_id: str, data: Any, user_id: bytes) -> MedicationCatalog:
    item = db.query(MedicationCatalog).filter(MedicationCatalog.id == item_id).first()
    if not item:
        raise not_found("Medication catalog entry not found.")
    old = model_to_dict(item)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    audit(db, user_id=user_id, tenant_id=tenant_id, action="UPDATE", table_name="medication_catalog", record_id=item.id, old_values=old, new_values=model_to_dict(item))
    commit_or_409(db)
    db.refresh(item)
    return item


def search_cie10(db: Session, q: str | None, limit: int = 20) -> list[Cie10Catalog]:
    query = db.query(Cie10Catalog).filter(Cie10Catalog.is_active.is_(True))
    if q:
        like = f"%{q}%"
        query = query.filter((Cie10Catalog.code.ilike(like)) | (Cie10Catalog.description.ilike(like)))
    return query.order_by(Cie10Catalog.code).limit(limit).all()


def create_cie10(db: Session, tenant_id: str, data: Any, user_id: bytes) -> Cie10Catalog:
    payload = data_for_model(data, Cie10Catalog)
    payload["id"] = new_uuid_bytes()
    item = Cie10Catalog(**payload)
    db.add(item)
    db.flush()
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="cie10_catalog", record_id=item.id, new_values=model_to_dict(item))
    commit_or_409(db)
    db.refresh(item)
    return item


def update_cie10(db: Session, item_id: bytes, tenant_id: str, data: Any, user_id: bytes) -> Cie10Catalog:
    item = db.query(Cie10Catalog).filter(Cie10Catalog.id == item_id).first()
    if not item:
        raise not_found("CIE-10 catalog entry not found.")
    old = model_to_dict(item)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    audit(db, user_id=user_id, tenant_id=tenant_id, action="UPDATE", table_name="cie10_catalog", record_id=item.id, old_values=old, new_values=model_to_dict(item))
    commit_or_409(db)
    db.refresh(item)
    return item


def list_lab_tests(db: Session) -> list[LabTestCatalog]:
    return db.query(LabTestCatalog).order_by(LabTestCatalog.test_name).all()


def create_lab_test(db: Session, tenant_id: str, data: Any, user_id: bytes) -> LabTestCatalog:
    payload = data_for_model(data, LabTestCatalog)
    payload["id"] = new_uuid_bytes()
    item = LabTestCatalog(**payload)
    db.add(item)
    db.flush()
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="lab_tests_catalog", record_id=item.id, new_values=model_to_dict(item))
    commit_or_409(db)
    db.refresh(item)
    return item


def update_lab_test(db: Session, item_id: bytes, tenant_id: str, data: Any, user_id: bytes) -> LabTestCatalog:
    item = db.query(LabTestCatalog).filter(LabTestCatalog.id == item_id).first()
    if not item:
        raise not_found("Lab test catalog entry not found.")
    old = model_to_dict(item)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    audit(db, user_id=user_id, tenant_id=tenant_id, action="UPDATE", table_name="lab_tests_catalog", record_id=item.id, old_values=old, new_values=model_to_dict(item))
    commit_or_409(db)
    db.refresh(item)
    return item


def list_clinical_systems(db: Session) -> list[ClinicalSystemCatalog]:
    return db.query(ClinicalSystemCatalog).order_by(ClinicalSystemCatalog.sort_order).all()


def create_clinical_system(db: Session, tenant_id: str, data: Any, user_id: bytes) -> ClinicalSystemCatalog:
    payload = data_for_model(data, ClinicalSystemCatalog)
    payload["id"] = new_uuid_bytes()
    item = ClinicalSystemCatalog(**payload)
    db.add(item)
    db.flush()
    audit(db, user_id=user_id, tenant_id=tenant_id, action="INSERT", table_name="clinical_systems_catalog", record_id=item.id, new_values=model_to_dict(item))
    commit_or_409(db)
    db.refresh(item)
    return item


def update_clinical_system(db: Session, item_id: bytes, tenant_id: str, data: Any, user_id: bytes) -> ClinicalSystemCatalog:
    item = db.query(ClinicalSystemCatalog).filter(ClinicalSystemCatalog.id == item_id).first()
    if not item:
        raise not_found("Clinical system catalog entry not found.")
    old = model_to_dict(item)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    audit(db, user_id=user_id, tenant_id=tenant_id, action="UPDATE", table_name="clinical_systems_catalog", record_id=item.id, old_values=old, new_values=model_to_dict(item))
    commit_or_409(db)
    db.refresh(item)
    return item
