"""
Grupo B: Tenant.status (active/suspended/archived) reemplaza el booleano
is_active. "suspended" y "archived" cortan sesion igual (403, mismo
mecanismo de H-09); solo el listado del owner distingue: archived se
oculta por defecto.

Requiere que la migracion tenant 0002_tenant_status.sql (que depende de
0001_catalog_columns.sql) ya este aplicada contra clinica_qa_norte:

    python scripts/migrate.py tenant up --only salvio_clinica_qa_norte

Sin esa migracion, TODOS los tests de este archivo (y de hecho cualquier
endpoint que use get_current_user) fallan con 500 (columna "status"
desconocida) -- el ORM ya espera la columna nueva.
"""

from conftest import BASE_URL, QA_DOCTOR_EMAIL, QA_PASSWORD, QA_TENANT, auth_headers, login, platform_admin_login


def test_suspended_tenant_blocks_login(api):
    platform_token = platform_admin_login(api)
    try:
        resp = api.patch(f"{BASE_URL}/api/v1/tenants/{QA_TENANT}", json={"status": "suspended"}, headers=auth_headers(platform_token))
        resp.raise_for_status()
        assert resp.json()["status"] == "suspended"

        login_attempt = api.post(f"{BASE_URL}/api/v1/auth/login", json={"tenant_id": QA_TENANT, "email": QA_DOCTOR_EMAIL, "password": QA_PASSWORD})
        assert login_attempt.status_code == 403
    finally:
        api.patch(f"{BASE_URL}/api/v1/tenants/{QA_TENANT}", json={"status": "active"}, headers=auth_headers(platform_token)).raise_for_status()

    login_again = login(api, QA_TENANT, QA_DOCTOR_EMAIL, QA_PASSWORD)
    assert login_again["access_token"]


def test_archived_tenant_hidden_from_default_listing(api):
    platform_token = platform_admin_login(api)
    try:
        resp = api.patch(f"{BASE_URL}/api/v1/tenants/{QA_TENANT}", json={"status": "archived"}, headers=auth_headers(platform_token))
        resp.raise_for_status()

        default_list = api.get(f"{BASE_URL}/api/v1/tenants", headers=auth_headers(platform_token))
        default_list.raise_for_status()
        assert all(t["tenant_id"] != QA_TENANT for t in default_list.json())

        full_list = api.get(f"{BASE_URL}/api/v1/tenants", params={"include_archived": "true"}, headers=auth_headers(platform_token))
        full_list.raise_for_status()
        assert any(t["tenant_id"] == QA_TENANT for t in full_list.json())

        login_attempt = api.post(f"{BASE_URL}/api/v1/auth/login", json={"tenant_id": QA_TENANT, "email": QA_DOCTOR_EMAIL, "password": QA_PASSWORD})
        assert login_attempt.status_code == 403
    finally:
        api.patch(f"{BASE_URL}/api/v1/tenants/{QA_TENANT}", json={"status": "active"}, headers=auth_headers(platform_token)).raise_for_status()

    login_again = login(api, QA_TENANT, QA_DOCTOR_EMAIL, QA_PASSWORD)
    assert login_again["access_token"]
