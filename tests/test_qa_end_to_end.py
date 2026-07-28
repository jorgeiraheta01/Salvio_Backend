"""
Objetivo 3: validacion QA end-to-end de la logica de negocio. A diferencia
de test_smoke_all_endpoints.py (un create-then-read aislado por grupo) y
de los test_*_lifecycle.py (CRUD completo de UNA entidad), este archivo
encadena varias entidades en un solo flujo realista para probar la
INTEGRACION entre ellas -- exactamente el tipo de bug que un test aislado
por entidad no puede detectar (ej. que una factura pendiente bloquee el
archivado de un paciente, algo que solo se ve si el flujo real crea
ambas cosas en orden).

Flujo: crear paciente -> agendar cita -> iniciar encuentro -> ordenar lab
-> facturar -> cerrar encuentro (requiere diagnostico + nota cerrada) ->
completar cita -> pagar factura -> archivar paciente (debe funcionar
porque para entonces no queda nada abierto).
"""

import time
from datetime import datetime, timedelta, timezone

from conftest import BASE_URL, QA_DOCTOR_EMAIL, QA_PASSWORD, QA_TENANT, QA_ADMIN_EMAIL, auth_headers, create_test_patient, get_doctor_id, login


def test_full_patient_lifecycle_end_to_end(api):
    admin_token = login(api, QA_TENANT, QA_ADMIN_EMAIL, QA_PASSWORD)["access_token"]
    doctor_token = login(api, QA_TENANT, QA_DOCTOR_EMAIL, QA_PASSWORD)["access_token"]
    doctor_id = get_doctor_id(api, admin_token)

    # 1. Crear paciente
    patient = create_test_patient(api, admin_token, unique_seed=int(time.time() * 1000) % 10**8)
    patient_id = patient["id"]

    # 2. Agendar cita
    appt = api.post(
        f"{BASE_URL}/api/v1/appointments",
        json={
            "tenant_id": QA_TENANT,
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
        headers=auth_headers(admin_token),
    )
    assert appt.status_code == 201
    appointment_id = appt.json()["id"]

    # Mientras la cita esta abierta, el paciente NO se puede archivar (H-05)
    blocked = api.delete(f"{BASE_URL}/api/v1/patients/{patient_id}", headers=auth_headers(admin_token))
    assert blocked.status_code == 409

    # 3. Iniciar encuentro ligado a esa cita
    encounter = api.post(
        f"{BASE_URL}/api/v1/encounters/start",
        json={"appointment_id": appointment_id, "chief_complaint": "QA e2e flow"},
        headers=auth_headers(doctor_token),
    )
    assert encounter.status_code == 201
    encounter_id = encounter.json()["id"]
    # start_encounter sincroniza la cita a in_consultation
    assert encounter.json()["status"] == "active"

    # 4. Ordenar laboratorio
    lab_order = api.post(
        f"{BASE_URL}/api/v1/lab-orders",
        json={"tenant_id": QA_TENANT, "patient_id": patient_id, "ordered_by": doctor_id, "test_name": "QA e2e CBC"},
        headers=auth_headers(doctor_token),
    )
    assert lab_order.status_code == 201
    lab_order_id = lab_order.json()["id"]

    # 5. Facturar -- mientras la factura este pendiente, tampoco se archiva (H-05)
    billing = api.post(
        f"{BASE_URL}/api/v1/billing",
        json={
            "tenant_id": QA_TENANT,
            "patient_id": patient_id,
            "items": [{"tenant_id": QA_TENANT, "description": "QA e2e consultation", "quantity": 1, "unit_price": 30}],
        },
        headers=auth_headers(admin_token),
    )
    assert billing.status_code == 201
    billing_id = billing.json()["id"]
    billing_amount = billing.json()["amount"]

    still_blocked = api.delete(f"{BASE_URL}/api/v1/patients/{patient_id}", headers=auth_headers(admin_token))
    assert still_blocked.status_code == 409

    # 6. Cerrar el encuentro requiere diagnostico + nota clinica cerrada
    diagnosis = api.post(
        f"{BASE_URL}/api/v1/diagnoses",
        json={"encounter_id": encounter_id, "code": "J00", "description": "QA e2e diagnosis", "type": "definitive", "classification": "primary", "is_first_time": True},
        headers=auth_headers(doctor_token),
    )
    assert diagnosis.status_code == 201

    note = api.post(
        f"{BASE_URL}/api/v1/clinical-notes",
        json={"encounter_id": encounter_id, "note_type": "progress", "content": "QA e2e note content."},
        headers=auth_headers(doctor_token),
    )
    assert note.status_code == 201
    note_id = note.json()["id"]
    close_note = api.post(f"{BASE_URL}/api/v1/clinical-notes/{note_id}/close", json={"version": 1}, headers=auth_headers(doctor_token))
    assert close_note.status_code == 200

    close_encounter = api.post(f"{BASE_URL}/api/v1/encounters/{encounter_id}/close", json={"version": 1}, headers=auth_headers(doctor_token))
    assert close_encounter.status_code == 200
    assert close_encounter.json()["status"] == "closed"

    # Cerrar el encuentro sincroniza la cita a completed
    appt_after_close = api.get(f"{BASE_URL}/api/v1/appointments", params={"patient_id": patient_id}, headers=auth_headers(admin_token))
    assert appt_after_close.status_code == 200
    matching = next(a for a in appt_after_close.json() if a["id"] == appointment_id)
    assert matching["status"] == "completed"

    # El paciente sigue bloqueado -- la factura pendiente sigue abierta
    still_blocked_2 = api.delete(f"{BASE_URL}/api/v1/patients/{patient_id}", headers=auth_headers(admin_token))
    assert still_blocked_2.status_code == 409

    # 7. Marcar el resultado de lab como completado (H-04)
    lab_step1 = api.patch(f"{BASE_URL}/api/v1/lab-orders/{lab_order_id}/status", json={"status": "collected"}, headers=auth_headers(doctor_token))
    assert lab_step1.status_code == 200
    lab_step2 = api.patch(f"{BASE_URL}/api/v1/lab-orders/{lab_order_id}/status", json={"status": "processing"}, headers=auth_headers(doctor_token))
    assert lab_step2.status_code == 200
    lab_step3 = api.patch(f"{BASE_URL}/api/v1/lab-orders/{lab_order_id}/status", json={"status": "completed"}, headers=auth_headers(doctor_token))
    assert lab_step3.status_code == 200

    # 8. Pagar la factura completa
    payment = api.post(
        f"{BASE_URL}/api/v1/billing/{billing_id}/payments",
        json={"tenant_id": QA_TENANT, "billing_id": billing_id, "amount": billing_amount, "payment_method": "cash"},
        headers=auth_headers(admin_token),
    )
    assert payment.status_code == 201
    billing_after = api.get(f"{BASE_URL}/api/v1/billing/{billing_id}", headers=auth_headers(admin_token))
    assert billing_after.json()["status"] == "paid"

    # 9. Ahora si -- sin citas abiertas, sin encuentro activo, sin factura
    # pendiente -- el paciente se puede archivar
    archived = api.delete(f"{BASE_URL}/api/v1/patients/{patient_id}", headers=auth_headers(admin_token))
    assert archived.status_code == 204

    # 10. Verificacion negativa: operar sobre el paciente ya archivado falla limpio
    get_after = api.get(f"{BASE_URL}/api/v1/patients/{patient_id}", headers=auth_headers(admin_token))
    assert get_after.status_code == 404

    billing_after_archive = api.post(
        f"{BASE_URL}/api/v1/billing",
        json={"tenant_id": QA_TENANT, "patient_id": patient_id, "items": [{"tenant_id": QA_TENANT, "description": "post-archive", "quantity": 1, "unit_price": 10}]},
        headers=auth_headers(admin_token),
    )
    assert billing_after_archive.status_code == 404
