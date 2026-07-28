"""
H-07: los catalogos (medicamentos, examenes de lab, sistemas clinicos)
existian como tablas -- usadas solo como FK -- sin ningun CRUD. Requiere
que la migracion tenant 0001_catalog_columns ya este aplicada
(sql/migrations/tenant/0001_catalog_columns.sql) contra clinica_qa_norte:

    python scripts/migrate.py tenant up --only salvio_clinica_qa_norte

Si no esta aplicada, estos tests fallan con 500 (columna desconocida) en
vez de fallar por una razon relacionada al CRUD en si.
"""

import time

from conftest import BASE_URL, QA_PASSWORD, QA_TENANT, QA_ADMIN_EMAIL, auth_headers, login


def _admin_token(api) -> str:
    return login(api, QA_TENANT, QA_ADMIN_EMAIL, QA_PASSWORD)["access_token"]


def test_medication_catalog_crud(api):
    token = _admin_token(api)
    seed = int(time.time() * 1000) % 10**8

    create = api.post(
        f"{BASE_URL}/api/v1/catalogs/medications",
        json={"generic_name": f"Test Med {seed}", "pharmaceutical_form": "tablet"},
        headers=auth_headers(token),
    )
    assert create.status_code == 201
    item_id = create.json()["id"]

    listed = api.get(f"{BASE_URL}/api/v1/catalogs/medications", headers=auth_headers(token))
    assert listed.status_code == 200
    assert any(m["id"] == item_id for m in listed.json())

    updated = api.patch(f"{BASE_URL}/api/v1/catalogs/medications/{item_id}", json={"is_active": False}, headers=auth_headers(token))
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False


def test_lab_test_catalog_crud(api):
    token = _admin_token(api)
    seed = int(time.time() * 1000) % 10**8

    create = api.post(
        f"{BASE_URL}/api/v1/catalogs/lab-tests",
        json={"test_code": f"T{seed}", "test_name": "Test Lab Test", "sample_type": "blood"},
        headers=auth_headers(token),
    )
    assert create.status_code == 201
    item_id = create.json()["id"]
    assert create.json()["sample_type"] == "blood"

    updated = api.patch(f"{BASE_URL}/api/v1/catalogs/lab-tests/{item_id}", json={"is_active": False}, headers=auth_headers(token))
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False


def test_clinical_system_catalog_crud(api):
    token = _admin_token(api)
    seed = int(time.time() * 1000) % 10**8

    create = api.post(
        f"{BASE_URL}/api/v1/catalogs/clinical-systems",
        json={"system_name": f"Test System {seed}", "description": "Test description"},
        headers=auth_headers(token),
    )
    assert create.status_code == 201
    item_id = create.json()["id"]
    assert create.json()["description"] == "Test description"

    updated = api.patch(f"{BASE_URL}/api/v1/catalogs/clinical-systems/{item_id}", json={"is_active": False}, headers=auth_headers(token))
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False
