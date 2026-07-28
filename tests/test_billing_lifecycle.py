"""
H-06: create_billing debe rechazar un patient_id inexistente o archivado.
H-03: BillingUpdate (ya existia el schema, no estaba conectado) ahora se
puede usar para anular una factura, con una allow-list de transiciones.
"""

import time
import uuid

from conftest import BASE_URL, QA_PASSWORD, QA_TENANT, QA_ADMIN_EMAIL, auth_headers, create_test_patient, login


def _admin_token(api) -> str:
    return login(api, QA_TENANT, QA_ADMIN_EMAIL, QA_PASSWORD)["access_token"]


def _create_billing(api, token: str, patient_id: str) -> dict:
    payload = {
        "tenant_id": QA_TENANT,
        "patient_id": patient_id,
        "items": [{"tenant_id": QA_TENANT, "description": "Test service", "quantity": 1, "unit_price": 25}],
    }
    return api.post(f"{BASE_URL}/api/v1/billing", json=payload, headers=auth_headers(token))


def test_create_billing_rejects_nonexistent_patient(api):
    token = _admin_token(api)
    resp = _create_billing(api, token, str(uuid.uuid4()))
    assert resp.status_code == 404


def test_create_billing_rejects_archived_patient(api):
    token = _admin_token(api)
    patient = create_test_patient(api, token, unique_seed=int(time.time() * 1000) % 10**8)
    del_resp = api.delete(f"{BASE_URL}/api/v1/patients/{patient['id']}", headers=auth_headers(token))
    assert del_resp.status_code == 204
    resp = _create_billing(api, token, patient["id"])
    assert resp.status_code == 404


def test_void_billing_requires_reason_and_is_final(api):
    token = _admin_token(api)
    patient = create_test_patient(api, token, unique_seed=int(time.time() * 1000) % 10**8)
    billing = _create_billing(api, token, patient["id"])
    assert billing.status_code == 201
    billing_id = billing.json()["id"]

    # void sin void_reason -> rechazado por el validator del schema (422)
    bad = api.patch(f"{BASE_URL}/api/v1/billing/{billing_id}", json={"status": "void"}, headers=auth_headers(token))
    assert bad.status_code == 422

    good = api.patch(f"{BASE_URL}/api/v1/billing/{billing_id}", json={"status": "void", "void_reason": "Test cancellation"}, headers=auth_headers(token))
    assert good.status_code == 200
    assert good.json()["status"] == "void"

    # void -> paid ya no es una transicion legal (void es terminal)
    illegal = api.patch(f"{BASE_URL}/api/v1/billing/{billing_id}", json={"status": "paid"}, headers=auth_headers(token))
    assert illegal.status_code == 422
