"""
H-01/H-02: users.py solo tenia GET -- no habia forma de editar, desactivar
ni reactivar un medico. Ahora existen PATCH /{id}, /{id}/deactivate y
/{id}/reactivate, con un chequeo de cascada pragmatico (bloquea si el
medico tiene citas futuras/abiertas o un encuentro activo).

Usa al medico QA real (iportillo@qanorte.dev) porque no existe un POST
para crear usuarios nuevos -- por eso el test SIEMPRE reactiva al final
(finally), incluso si una aseveracion intermedia falla, para no dejar
inutilizable la cuenta que otros tests tambien usan.
"""

import time
from datetime import datetime, timedelta, timezone

import pymysql

from conftest import BASE_URL, DB_HOST, DB_PASSWORD, DB_USER, QA_DOCTOR_EMAIL, QA_PASSWORD, QA_TENANT, QA_ADMIN_EMAIL, auth_headers, create_test_patient, get_doctor_id, login


def _admin_token(api) -> str:
    return login(api, QA_TENANT, QA_ADMIN_EMAIL, QA_PASSWORD)["access_token"]


def _force_close_active_encounters(doctor_id: str) -> None:
    """Este stack de tests corre contra la BD real compartida (ver
    conftest.py) -- encuentros activos de sesiones de QA anteriores para este
    mismo medico bloquearian legitimamente el chequeo de cascada de
    deactivate_user, pero cerrarlos "de verdad" via la API exige
    diagnostico + nota clinica cerrada, que no es lo que este test valida.
    Se fuerza el cierre por SQL directo, solo higiene de datos de prueba."""
    conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=f"salvio_{QA_TENANT}")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE encounters SET status='closed', closed_at=NOW() WHERE status='active' AND doctor_id = UUID_TO_BIN(%s)",
                (doctor_id,),
            )
        conn.commit()
    finally:
        conn.close()


def test_update_user_profile_fields(api):
    admin_token = _admin_token(api)
    doctor_id = get_doctor_id(api, admin_token)

    get_before = api.get(f"{BASE_URL}/api/v1/users", headers=auth_headers(admin_token), params={"role": "doctor"})
    original_specialty = next(u["specialty"] for u in get_before.json() if u["id"] == doctor_id)

    try:
        resp = api.patch(f"{BASE_URL}/api/v1/users/{doctor_id}", json={"specialty": "Test Cardiology"}, headers=auth_headers(admin_token))
        assert resp.status_code == 200
        assert resp.json()["specialty"] == "Test Cardiology"
    finally:
        api.patch(f"{BASE_URL}/api/v1/users/{doctor_id}", json={"specialty": original_specialty}, headers=auth_headers(admin_token))


def test_deactivate_blocked_by_open_appointment_then_succeeds_when_clean(api):
    admin_token = _admin_token(api)
    doctor_id = get_doctor_id(api, admin_token)
    seed = int(time.time() * 1000) % 10**8
    patient = create_test_patient(api, admin_token, unique_seed=seed)

    appt = api.post(
        f"{BASE_URL}/api/v1/appointments",
        json={
            "tenant_id": QA_TENANT,
            "patient_id": patient["id"],
            "doctor_id": doctor_id,
            # dia 8 (no 7, para no chocar con test_patient_lifecycle.py) +
            # offset por seed, mismo motivo: BD compartida sin aislamiento
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=8, minutes=seed % 500)).isoformat(),
        },
        headers=auth_headers(admin_token),
    )
    assert appt.status_code == 201
    appointment_id = appt.json()["id"]

    try:
        blocked = api.patch(f"{BASE_URL}/api/v1/users/{doctor_id}/deactivate", headers=auth_headers(admin_token))
        assert blocked.status_code == 409

        # Este stack de tests corre contra la BD real compartida (sin
        # aislamiento por test, ver conftest.py) -- puede haber otras citas
        # futuras abiertas del mismo medico dejadas por otros tests (ej.
        # test_patient_lifecycle.py). Cancelar todas, no solo la propia, para
        # que este test no dependa de que nadie mas haya dejado basura.
        open_appts = api.get(
            f"{BASE_URL}/api/v1/appointments",
            headers=auth_headers(admin_token),
            params={"doctor_id": doctor_id},
        )
        assert open_appts.status_code == 200
        now = datetime.now(timezone.utc)
        for a in open_appts.json():
            scheduled_at = datetime.fromisoformat(a["scheduled_at"].replace("Z", "+00:00"))
            if scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
            # Solo cancelar futuras -- coincide exactamente con el criterio de
            # bloqueo de deactivate_user. Una in_consultation pasada no cuenta
            # como abierta para ese chequeo y ademas no admite "cancelled"
            # como transicion legal (solo "completed").
            if scheduled_at >= now and a["status"] in {"scheduled", "confirmed", "checked_in"}:
                cancel = api.patch(
                    f"{BASE_URL}/api/v1/appointments/{a['id']}/status",
                    json={"status": "cancelled", "reason": "test cleanup"},
                    headers=auth_headers(admin_token),
                )
                assert cancel.status_code == 200

        _force_close_active_encounters(doctor_id)

        deactivated = api.patch(f"{BASE_URL}/api/v1/users/{doctor_id}/deactivate", headers=auth_headers(admin_token))
        assert deactivated.status_code == 200
        assert deactivated.json()["is_active"] is False

        login_attempt = api.post(f"{BASE_URL}/api/v1/auth/login", json={"tenant_id": QA_TENANT, "email": QA_DOCTOR_EMAIL, "password": QA_PASSWORD})
        assert login_attempt.status_code == 401
    finally:
        reactivated = api.patch(f"{BASE_URL}/api/v1/users/{doctor_id}/reactivate", headers=auth_headers(admin_token))
        assert reactivated.status_code == 200
        assert reactivated.json()["is_active"] is True

    login_again = login(api, QA_TENANT, QA_DOCTOR_EMAIL, QA_PASSWORD)
    assert login_again["access_token"]
