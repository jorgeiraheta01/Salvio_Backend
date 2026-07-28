"""
H-05: soft_delete_patient (archivar) ahora bloquea si el paciente tiene una
cita futura/abierta, un encuentro activo, o una factura pendiente -- antes
no habia ningun chequeo de cascada.
"""

import time
from datetime import datetime, timedelta, timezone

from conftest import BASE_URL, QA_PASSWORD, QA_TENANT, QA_ADMIN_EMAIL, auth_headers, create_test_patient, get_doctor_id, login


def _admin_token(api) -> str:
    return login(api, QA_TENANT, QA_ADMIN_EMAIL, QA_PASSWORD)["access_token"]


def test_archive_blocked_by_open_appointment(api):
    token = _admin_token(api)
    doctor_id = get_doctor_id(api, token)
    patient = create_test_patient(api, token, unique_seed=int(time.time() * 1000) % 10**8)

    appt = api.post(
        f"{BASE_URL}/api/v1/appointments",
        json={
            "tenant_id": QA_TENANT,
            "patient_id": patient["id"],
            "doctor_id": doctor_id,
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        },
        headers=auth_headers(token),
    )
    assert appt.status_code == 201

    archive = api.delete(f"{BASE_URL}/api/v1/patients/{patient['id']}", headers=auth_headers(token))
    assert archive.status_code == 409


def test_archive_blocked_by_pending_billing(api):
    token = _admin_token(api)
    patient = create_test_patient(api, token, unique_seed=int(time.time() * 1000) % 10**8)

    billing = api.post(
        f"{BASE_URL}/api/v1/billing",
        json={
            "tenant_id": QA_TENANT,
            "patient_id": patient["id"],
            "items": [{"tenant_id": QA_TENANT, "description": "Test service", "quantity": 1, "unit_price": 10}],
        },
        headers=auth_headers(token),
    )
    assert billing.status_code == 201

    archive = api.delete(f"{BASE_URL}/api/v1/patients/{patient['id']}", headers=auth_headers(token))
    assert archive.status_code == 409


def test_archive_succeeds_when_clean(api):
    token = _admin_token(api)
    patient = create_test_patient(api, token, unique_seed=int(time.time() * 1000) % 10**8)

    archive = api.delete(f"{BASE_URL}/api/v1/patients/{patient['id']}", headers=auth_headers(token))
    assert archive.status_code == 204

    get_after = api.get(f"{BASE_URL}/api/v1/patients/{patient['id']}", headers=auth_headers(token))
    assert get_after.status_code == 404
