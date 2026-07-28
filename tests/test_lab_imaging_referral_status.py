"""
H-04: lab-orders/imaging-studies/referrals ahora tienen un PATCH de estado
con una allow-list de transiciones (antes: el estado se fijaba al crear y
nunca cambiaba, InterconsultRespond/ReferralUpdate existian sin conectar).
"""

import time

from conftest import BASE_URL, QA_DOCTOR_EMAIL, QA_PASSWORD, QA_TENANT, QA_ADMIN_EMAIL, auth_headers, create_test_patient, get_doctor_id, login


def _tokens(api):
    admin_token = login(api, QA_TENANT, QA_ADMIN_EMAIL, QA_PASSWORD)["access_token"]
    doctor_token = login(api, QA_TENANT, QA_DOCTOR_EMAIL, QA_PASSWORD)["access_token"]
    return admin_token, doctor_token


def test_lab_order_status_transitions(api):
    admin_token, doctor_token = _tokens(api)
    patient = create_test_patient(api, admin_token, unique_seed=int(time.time() * 1000) % 10**8)
    doctor_id = get_doctor_id(api, admin_token)

    create = api.post(
        f"{BASE_URL}/api/v1/lab-orders",
        json={"tenant_id": QA_TENANT, "patient_id": patient["id"], "ordered_by": doctor_id, "test_name": "CBC"},
        headers=auth_headers(doctor_token),
    )
    assert create.status_code == 201
    order_id = create.json()["id"]

    illegal = api.patch(f"{BASE_URL}/api/v1/lab-orders/{order_id}/status", json={"status": "completed"}, headers=auth_headers(doctor_token))
    assert illegal.status_code == 422

    step1 = api.patch(f"{BASE_URL}/api/v1/lab-orders/{order_id}/status", json={"status": "collected"}, headers=auth_headers(doctor_token))
    assert step1.status_code == 200
    assert step1.json()["status"] == "collected"

    step2 = api.patch(f"{BASE_URL}/api/v1/lab-orders/{order_id}/status", json={"status": "processing"}, headers=auth_headers(doctor_token))
    assert step2.status_code == 200

    step3 = api.patch(f"{BASE_URL}/api/v1/lab-orders/{order_id}/status", json={"status": "completed"}, headers=auth_headers(doctor_token))
    assert step3.status_code == 200

    reopen = api.patch(f"{BASE_URL}/api/v1/lab-orders/{order_id}/status", json={"status": "ordered"}, headers=auth_headers(doctor_token))
    assert reopen.status_code == 422


def test_imaging_study_status_transitions(api):
    admin_token, doctor_token = _tokens(api)
    patient = create_test_patient(api, admin_token, unique_seed=int(time.time() * 1000) % 10**8)

    create = api.post(
        f"{BASE_URL}/api/v1/imaging-studies",
        json={"tenant_id": QA_TENANT, "patient_id": patient["id"], "study_type": "X-Ray"},
        headers=auth_headers(doctor_token),
    )
    assert create.status_code == 201
    study_id = create.json()["id"]

    illegal = api.patch(f"{BASE_URL}/api/v1/imaging-studies/{study_id}/status", json={"status": "reviewed"}, headers=auth_headers(doctor_token))
    assert illegal.status_code == 422

    step1 = api.patch(f"{BASE_URL}/api/v1/imaging-studies/{study_id}/status", json={"status": "performed"}, headers=auth_headers(doctor_token))
    assert step1.status_code == 200

    step2 = api.patch(f"{BASE_URL}/api/v1/imaging-studies/{study_id}/status", json={"status": "reviewed"}, headers=auth_headers(doctor_token))
    assert step2.status_code == 200

    reopen = api.patch(f"{BASE_URL}/api/v1/imaging-studies/{study_id}/status", json={"status": "performed"}, headers=auth_headers(doctor_token))
    assert reopen.status_code == 422


def test_referral_status_transitions(api):
    admin_token, doctor_token = _tokens(api)
    patient = create_test_patient(api, admin_token, unique_seed=int(time.time() * 1000) % 10**8)

    create = api.post(
        f"{BASE_URL}/api/v1/referrals",
        json={"tenant_id": QA_TENANT, "patient_id": patient["id"], "referral_type": "internal"},
        headers=auth_headers(doctor_token),
    )
    assert create.status_code == 201
    referral_id = create.json()["id"]

    illegal = api.patch(f"{BASE_URL}/api/v1/referrals/{referral_id}", json={"status": "completed"}, headers=auth_headers(doctor_token))
    assert illegal.status_code == 422

    accept = api.patch(f"{BASE_URL}/api/v1/referrals/{referral_id}", json={"status": "accepted"}, headers=auth_headers(doctor_token))
    assert accept.status_code == 200

    complete = api.patch(f"{BASE_URL}/api/v1/referrals/{referral_id}", json={"status": "completed"}, headers=auth_headers(doctor_token))
    assert complete.status_code == 200

    reopen = api.patch(f"{BASE_URL}/api/v1/referrals/{referral_id}", json={"status": "accepted"}, headers=auth_headers(doctor_token))
    assert reopen.status_code == 422


def test_interconsult_respond(api):
    admin_token, doctor_token = _tokens(api)
    patient = create_test_patient(api, admin_token, unique_seed=int(time.time() * 1000) % 10**8)
    doctor_id = get_doctor_id(api, admin_token)

    create = api.post(
        f"{BASE_URL}/api/v1/referrals/interconsults",
        json={
            "tenant_id": QA_TENANT,
            "patient_id": patient["id"],
            "requesting_doctor": doctor_id,
            "requesting_doctor_name": "Dr. QA",
            "consulting_specialty": "Cardiology",
        },
        headers=auth_headers(doctor_token),
    )
    assert create.status_code == 201
    interconsult_id = create.json()["id"]

    respond = api.patch(
        f"{BASE_URL}/api/v1/referrals/interconsults/{interconsult_id}/respond",
        json={"response": "Patient evaluated, no acute findings."},
        headers=auth_headers(doctor_token),
    )
    assert respond.status_code == 200
    assert respond.json()["status"] == "completed"
    assert respond.json()["response"] == "Patient evaluated, no acute findings."
