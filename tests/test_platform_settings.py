"""
Grupo C: modo mantenimiento, anuncios y feature flags para la consola del
owner. Requiere las migraciones control 0004/0005/0006 aplicadas:

    python scripts/migrate.py control up

Sin ellas, estos tests fallan (maintenance_mode defaultea a apagado sin
tabla -- ver app/middleware/maintenance.py -- pero announcements/feature-
flags si fallan con 500 sin sus tablas).
"""

import time

from conftest import BASE_URL, QA_DOCTOR_EMAIL, QA_PASSWORD, QA_TENANT, auth_headers, login, platform_admin_login


def test_maintenance_mode_blocks_tenant_but_not_owner(api):
    platform_token = platform_admin_login(api)
    try:
        enable = api.patch(
            f"{BASE_URL}/api/v1/platform-admin/maintenance-mode",
            json={"enabled": True, "message": "Mantenimiento de prueba"},
            headers=auth_headers(platform_token),
        )
        assert enable.status_code == 200
        assert enable.json()["enabled"] is True

        tenant_login = api.post(f"{BASE_URL}/api/v1/auth/login", json={"tenant_id": QA_TENANT, "email": QA_DOCTOR_EMAIL, "password": QA_PASSWORD})
        assert tenant_login.status_code == 503

        owner_still_works = api.get(f"{BASE_URL}/api/v1/tenants", headers=auth_headers(platform_token))
        assert owner_still_works.status_code == 200
    finally:
        api.patch(
            f"{BASE_URL}/api/v1/platform-admin/maintenance-mode",
            json={"enabled": False, "message": None},
            headers=auth_headers(platform_token),
        ).raise_for_status()

    login_again = login(api, QA_TENANT, QA_DOCTOR_EMAIL, QA_PASSWORD)
    assert login_again["access_token"]


def test_announcement_crud_and_tenant_visibility(api):
    platform_token = platform_admin_login(api)
    seed = int(time.time() * 1000) % 10**8

    create = api.post(
        f"{BASE_URL}/api/v1/platform-admin/announcements",
        json={"message": f"Test announcement {seed}", "severity": "info"},
        headers=auth_headers(platform_token),
    )
    assert create.status_code == 201
    announcement_id = create.json()["id"]

    doctor_token = login(api, QA_TENANT, QA_DOCTOR_EMAIL, QA_PASSWORD)["access_token"]
    active = api.get(f"{BASE_URL}/api/v1/announcements/active", headers=auth_headers(doctor_token))
    assert active.status_code == 200
    assert any(a["id"] == announcement_id for a in active.json())

    deactivate = api.patch(
        f"{BASE_URL}/api/v1/platform-admin/announcements/{announcement_id}",
        json={"active": False},
        headers=auth_headers(platform_token),
    )
    assert deactivate.status_code == 200

    active_after = api.get(f"{BASE_URL}/api/v1/announcements/active", headers=auth_headers(doctor_token))
    assert all(a["id"] != announcement_id for a in active_after.json())


def test_feature_flag_crud_and_tenant_visibility(api):
    platform_token = platform_admin_login(api)
    seed = int(time.time() * 1000) % 10**8
    key = f"test_flag_{seed}"

    create = api.post(
        f"{BASE_URL}/api/v1/platform-admin/feature-flags",
        json={"key": key, "enabled": True},
        headers=auth_headers(platform_token),
    )
    assert create.status_code == 201
    flag_id = create.json()["id"]

    doctor_token = login(api, QA_TENANT, QA_DOCTOR_EMAIL, QA_PASSWORD)["access_token"]
    flags = api.get(f"{BASE_URL}/api/v1/feature-flags", headers=auth_headers(doctor_token))
    assert flags.status_code == 200
    assert any(f["key"] == key and f["enabled"] for f in flags.json())

    disable = api.patch(
        f"{BASE_URL}/api/v1/platform-admin/feature-flags/{flag_id}",
        json={"enabled": False},
        headers=auth_headers(platform_token),
    )
    assert disable.status_code == 200
    assert disable.json()["enabled"] is False
