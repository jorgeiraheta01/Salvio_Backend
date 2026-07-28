"""
Objetivo 2 del barrido: smoke-test de la superficie de endpoints que
todavia no tenia NINGUNA cobertura (patients, appointments, encounters,
clinical-records + sub-recursos, clinical-notes, diagnoses, vital-signs,
orders, prescriptions, wa-messages). No es cobertura exhaustiva de los
~114 endpoints -- es la pasada de "mayor valor, menor esfuerzo": un
create-then-read por grupo, con datos reales de la clinica QA, para
detectar 500s/contratos rotos, no para validar cada regla de negocio
(eso ya lo hacen los test_*_lifecycle.py).

Reconciliacion de conteo: hay 114 endpoints totales bajo /api/v1/* + GET /
de salud (113 + 1), no "103" como se penso originalmente en el QA previo
de este proyecto.
"""

import time
from datetime import datetime, timedelta, timezone

from conftest import BASE_URL, QA_DOCTOR_EMAIL, QA_PASSWORD, QA_TENANT, QA_ADMIN_EMAIL, auth_headers, create_test_patient, get_doctor_id, login


def _tokens(api):
    admin_token = login(api, QA_TENANT, QA_ADMIN_EMAIL, QA_PASSWORD)["access_token"]
    doctor_token = login(api, QA_TENANT, QA_DOCTOR_EMAIL, QA_PASSWORD)["access_token"]
    return admin_token, doctor_token


def test_patients_list_detail_and_subresource_smoke(api):
    admin_token, _ = _tokens(api)
    patient = create_test_patient(api, admin_token, unique_seed=int(time.time() * 1000) % 10**8)

    listed = api.get(f"{BASE_URL}/api/v1/patients", headers=auth_headers(admin_token))
    assert listed.status_code == 200

    detail = api.get(f"{BASE_URL}/api/v1/patients/{patient['id']}", headers=auth_headers(admin_token))
    assert detail.status_code == 200

    allergy = api.post(
        f"{BASE_URL}/api/v1/patients/{patient['id']}/allergies",
        json={"patient_id": patient["id"], "tenant_id": QA_TENANT, "allergen": "Penicillin", "severity": "moderate"},
        headers=auth_headers(admin_token),
    )
    assert allergy.status_code == 201

    allergies_list = api.get(f"{BASE_URL}/api/v1/patients/{patient['id']}/allergies", headers=auth_headers(admin_token))
    assert allergies_list.status_code == 200
    assert len(allergies_list.json()) >= 1


def test_encounter_full_chain_smoke(api):
    """Cubre encounters, clinical-notes, diagnoses, vital-signs, orders y
    prescriptions en un solo flujo realista (crear paciente -> iniciar
    encuentro -> diagnostico + nota cerrada -> cerrar encuentro)."""
    admin_token, doctor_token = _tokens(api)
    patient = create_test_patient(api, admin_token, unique_seed=int(time.time() * 1000) % 10**8)

    start = api.post(
        f"{BASE_URL}/api/v1/encounters/start",
        json={"patient_id": patient["id"], "chief_complaint": "Smoke test"},
        headers=auth_headers(doctor_token),
    )
    assert start.status_code == 201
    encounter = start.json()
    encounter_id = encounter["id"]

    get_encounter = api.get(f"{BASE_URL}/api/v1/encounters/{encounter_id}", headers=auth_headers(doctor_token))
    assert get_encounter.status_code == 200

    list_encounters = api.get(f"{BASE_URL}/api/v1/encounters", params={"patient_id": patient["id"]}, headers=auth_headers(doctor_token))
    assert list_encounters.status_code == 200

    vital = api.post(
        f"{BASE_URL}/api/v1/vital-signs",
        json={"patient_id": patient["id"], "tenant_id": QA_TENANT, "encounter_id": encounter_id, "heart_rate": 72},
        headers=auth_headers(doctor_token),
    )
    assert vital.status_code == 201

    order = api.post(
        f"{BASE_URL}/api/v1/orders",
        json={"encounter_id": encounter_id, "order_type": "lab", "description": "Smoke test order"},
        headers=auth_headers(doctor_token),
    )
    assert order.status_code == 201

    diagnosis = api.post(
        f"{BASE_URL}/api/v1/diagnoses",
        json={
            "encounter_id": encounter_id,
            "code": "J00",
            "description": "Acute nasopharyngitis",
            "type": "definitive",
            "classification": "primary",
            "is_first_time": True,
        },
        headers=auth_headers(doctor_token),
    )
    assert diagnosis.status_code == 201

    diagnoses_list = api.get(f"{BASE_URL}/api/v1/diagnoses", params={"encounter_id": encounter_id}, headers=auth_headers(doctor_token))
    assert diagnoses_list.status_code == 200

    note = api.post(
        f"{BASE_URL}/api/v1/clinical-notes",
        json={"encounter_id": encounter_id, "note_type": "progress", "content": "Smoke test note content."},
        headers=auth_headers(doctor_token),
    )
    assert note.status_code == 201
    note_id = note.json()["id"]

    close_note = api.post(f"{BASE_URL}/api/v1/clinical-notes/{note_id}/close", json={"version": 1}, headers=auth_headers(doctor_token))
    assert close_note.status_code == 200

    prescription = api.post(
        f"{BASE_URL}/api/v1/prescriptions",
        json={
            "encounter_id": encounter_id,
            "prescribed_by_name": "Dr. QA",
            "medications": [{"medication_name": "Paracetamol", "dose": "500mg", "frequency": "8h", "route": "oral"}],
        },
        headers=auth_headers(doctor_token),
    )
    assert prescription.status_code == 201

    close = api.post(f"{BASE_URL}/api/v1/encounters/{encounter_id}/close", json={"version": 1}, headers=auth_headers(doctor_token))
    assert close.status_code == 200
    assert close.json()["status"] == "closed"


def test_wa_message_smoke(api):
    admin_token, _ = _tokens(api)
    patient = create_test_patient(api, admin_token, unique_seed=int(time.time() * 1000) % 10**8)

    consent = api.post(
        f"{BASE_URL}/api/v1/patients/{patient['id']}/consents",
        json={"patient_id": patient["id"], "tenant_id": QA_TENANT, "consent_type": "whatsapp", "consent_text": "Patient agreed to WhatsApp notifications."},
        headers=auth_headers(admin_token),
    )
    assert consent.status_code == 201

    create = api.post(
        f"{BASE_URL}/api/v1/wa-messages",
        json={"patient_id": patient["id"], "tenant_id": QA_TENANT, "message_type": "reminder"},
        headers=auth_headers(admin_token),
    )
    assert create.status_code == 201

    listed = api.get(f"{BASE_URL}/api/v1/wa-messages", headers=auth_headers(admin_token))
    assert listed.status_code == 200


def test_appointment_admission_and_triage_smoke(api):
    admin_token, doctor_token = _tokens(api)
    doctor_id = get_doctor_id(api, admin_token)
    patient = create_test_patient(api, admin_token, unique_seed=int(time.time() * 1000) % 10**8)

    appt = api.post(
        f"{BASE_URL}/api/v1/appointments",
        json={
            "tenant_id": QA_TENANT,
            "patient_id": patient["id"],
            "doctor_id": doctor_id,
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        },
        headers=auth_headers(admin_token),
    )
    assert appt.status_code == 201
    appointment_id = appt.json()["id"]

    admission = api.post(
        f"{BASE_URL}/api/v1/appointments/{appointment_id}/admissions",
        json={
            "patient_id": patient["id"],
            "tenant_id": QA_TENANT,
            "admission_datetime": datetime.now(timezone.utc).isoformat(),
        },
        headers=auth_headers(admin_token),
    )
    assert admission.status_code == 201

    triage = api.post(
        f"{BASE_URL}/api/v1/appointments/{appointment_id}/triage",
        json={
            "patient_id": patient["id"],
            "tenant_id": QA_TENANT,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "priority": "moderate",
        },
        headers=auth_headers(doctor_token),
    )
    assert triage.status_code == 201

    # limpieza -- no dejar esta cita futura bloqueando deactivate_user en
    # otros tests (ver test_user_lifecycle.py)
    api.patch(
        f"{BASE_URL}/api/v1/appointments/{appointment_id}/status",
        json={"status": "cancelled", "reason": "smoke test cleanup"},
        headers=auth_headers(admin_token),
    )


def test_clinical_record_crud_smoke(api):
    admin_token, doctor_token = _tokens(api)
    doctor_id = get_doctor_id(api, admin_token)
    patient = create_test_patient(api, admin_token, unique_seed=int(time.time() * 1000) % 10**8)

    create = api.post(
        f"{BASE_URL}/api/v1/clinical-records",
        json={"patient_id": patient["id"], "tenant_id": QA_TENANT, "doctor_id": doctor_id, "doctor_name": "Dr. QA", "soap_subjective": "Smoke test"},
        headers=auth_headers(doctor_token),
    )
    assert create.status_code == 201
    record_id = create.json()["id"]

    detail = api.get(f"{BASE_URL}/api/v1/clinical-records/{record_id}", headers=auth_headers(doctor_token))
    assert detail.status_code == 200

    update = api.patch(f"{BASE_URL}/api/v1/clinical-records/{record_id}", json={"soap_plan": "Smoke test plan"}, headers=auth_headers(doctor_token))
    assert update.status_code == 200

    vitals = api.get(f"{BASE_URL}/api/v1/clinical-records/{record_id}/vital-signs", headers=auth_headers(doctor_token))
    assert vitals.status_code == 200


# --- Hallazgos documentados durante la investigacion (no se arreglan aqui,
# solo se deja constancia de su comportamiento actual) ---


def test_documented_finding_2fa_verify_is_dead_code(api):
    """auth.py::login() hardcodea requires_2fa=False -- /auth/2fa/verify
    nunca es alcanzable desde el flujo normal de login de un usuario de
    clinica. H-15 ya documenta esto como decision pendiente, no bug nuevo."""
    resp = api.post(f"{BASE_URL}/api/v1/auth/login", json={"tenant_id": QA_TENANT, "email": QA_DOCTOR_EMAIL, "password": QA_PASSWORD})
    assert resp.status_code == 200
    assert resp.json()["requires_2fa"] is False


def test_documented_finding_prescriptions_list_is_role_gated(api):
    """GET /api/v1/prescriptions exige rol (doctor/resident/nurse), a
    diferencia de casi todos los demas endpoints de listado que solo piden
    JWT valido (cualquier rol autenticado) -- confirmado, no se cambia
    aqui (podria ser deliberado por ser data clinica sensible)."""
    admin_token, _ = _tokens(api)
    resp = api.get(f"{BASE_URL}/api/v1/prescriptions", headers=auth_headers(admin_token))
    assert resp.status_code == 403


def test_documented_finding_public_access_token_unwired(api):
    """PublicAccessToken (referrals) no tiene ninguna ruta que lo exponga --
    confirmado, no una regresion de este barrido."""
    resp = api.get(f"{BASE_URL}/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert not any("public-access" in p or "public_access" in p for p in paths)
