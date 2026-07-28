"""
Grupo A: toda accion del owner de la plataforma debe quedar en
audit_log dentro de salvio_control (antes: cero acciones del owner
dejaban rastro -- ni login, ni crear clinica, ni editar clinica).
"""

import pymysql
import pytest

from conftest import BASE_URL, PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_PASSWORD, QA_TENANT, auth_headers, platform_admin_login


def _count_control_audit_rows(action: str, tenant_id: str | None = None) -> int:
    conn = pymysql.connect(host="127.0.0.1", user="root", password="rootroot", database="salvio_control")
    try:
        with conn.cursor() as cur:
            if tenant_id:
                cur.execute("SELECT COUNT(*) FROM audit_log WHERE action = %s AND tenant_id = %s", (action, tenant_id))
            else:
                cur.execute("SELECT COUNT(*) FROM audit_log WHERE action = %s", (action,))
            return cur.fetchone()[0]
    finally:
        conn.close()


def test_successful_login_is_audited(api):
    before = _count_control_audit_rows("login")
    platform_admin_login(api)
    after = _count_control_audit_rows("login")
    assert after == before + 1


def test_failed_login_is_audited(api):
    before = _count_control_audit_rows("login_failed")
    resp = api.post(f"{BASE_URL}/api/v1/platform-admin/login", json={"email": PLATFORM_ADMIN_EMAIL, "password": "definitely-wrong"})
    assert resp.status_code == 401
    after = _count_control_audit_rows("login_failed")
    assert after == before + 1


def test_update_tenant_is_audited(api):
    token = platform_admin_login(api)
    before = _count_control_audit_rows("update_tenant", tenant_id=QA_TENANT)
    resp = api.patch(
        f"{BASE_URL}/api/v1/tenants/{QA_TENANT}",
        json={"name": "Clinica QA Norte"},  # no-op: mismo nombre, solo para generar la auditoria
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    after = _count_control_audit_rows("update_tenant", tenant_id=QA_TENANT)
    assert after == before + 1
