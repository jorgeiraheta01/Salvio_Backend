"""
Grupo D: dashboard agregado del owner -- solo conteos/sumas por clinica,
nunca contenido clinico individual (nombres de pacientes, etc.), segun lo
ya aprobado. Requiere que la migracion tenant 0002_tenant_status ya este
aplicada (el dashboard lee Tenant.status).
"""

from conftest import BASE_URL, QA_DOCTOR_EMAIL, QA_PASSWORD, QA_TENANT, auth_headers, login, platform_admin_login


def test_dashboard_returns_aggregated_counts_for_owner(api):
    platform_token = platform_admin_login(api)
    resp = api.get(f"{BASE_URL}/api/v1/tenants/dashboard", headers=auth_headers(platform_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "tenants" in data and "totals" in data
    qa_entry = next((t for t in data["tenants"] if t["tenant_id"] == QA_TENANT), None)
    assert qa_entry is not None
    assert qa_entry["patients_count"] >= 0
    assert qa_entry["appointments_count"] >= 0
    assert isinstance(qa_entry["billing_pending"], (int, float))
    # nunca contenido clinico individual -- solo agregados/conteos + identidad basica
    assert set(qa_entry.keys()) == {
        "tenant_id",
        "name",
        "status",
        "patients_count",
        "appointments_count",
        "encounters_count",
        "billing_pending",
        "billing_paid",
        "staff_count",
        "last_activity_at",
        "prescriptions_count",
        "lab_orders_count",
        "appointments_completed",
        "appointments_cancelled",
        "modules_active",
        "modules_total",
    }


def test_dashboard_is_owner_only(api):
    doctor_token = login(api, QA_TENANT, QA_DOCTOR_EMAIL, QA_PASSWORD)["access_token"]
    resp = api.get(f"{BASE_URL}/api/v1/tenants/dashboard", headers=auth_headers(doctor_token))
    assert resp.status_code == 403
