"""
Tests de integracion contra el backend real corriendo en local
(http://127.0.0.1:8000), no tests unitarios aislados.

Por que asi y no con TestClient + BD de pruebas aislada: la arquitectura es
DB-per-tenant (una base de datos MySQL fisica por clinica) y hoy no existe
infraestructura para provisionar/destruir una BD de tenant desechable por
test. Hasta que exista esa infraestructura, estos tests asumen:
  - El stack local esta arriba (docker compose + uvicorn + MySQL).
  - Existe el tenant "clinica_qa_norte" (creado durante el QA de esta sesion)
    con un admin y al menos un medico con las credenciales de abajo.
  - Existe el owner de plataforma "owner@salvio.dev".

Son tests reales end-to-end, no mocks. Confirman comportamiento, no
sustituyen tests unitarios rapidos que el proyecto todavia no tiene.
"""

import sys
from pathlib import Path

import pyotp
import pymysql
import pytest
import requests
from dotenv import load_dotenv

# Para poder importar app.utils.totp (reutiliza el mismo cifrado que el
# backend real) sin depender de donde se invoque pytest desde.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv()

from app.utils import totp as totp_utils  # noqa: E402

BASE_URL = "http://127.0.0.1:8000"
QA_TENANT = "clinica_qa_norte"
QA_ADMIN_EMAIL = "admin@qanorte.dev"
QA_DOCTOR_EMAIL = "iportillo@qanorte.dev"
QA_PASSWORD = "Test1234!"
PLATFORM_ADMIN_EMAIL = "owner@salvio.dev"
PLATFORM_ADMIN_PASSWORD = "SalvioOwner2026!"

# Mismos valores que scripts/migrate.py -- TODO compartido: leer de .env.
DB_HOST = "127.0.0.1"
DB_USER = "root"
DB_PASSWORD = "rootroot"


@pytest.fixture(scope="session")
def api():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def login(api, tenant_id: str, email: str, password: str) -> dict:
    resp = api.post(f"{BASE_URL}/api/v1/auth/login", json={"tenant_id": tenant_id, "email": email, "password": password})
    resp.raise_for_status()
    return resp.json()


def _platform_admin_totp_secret(email: str) -> str:
    conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database="salvio_control")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT totp_secret_encrypted FROM platform_admins WHERE email = %s", (email,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        raise RuntimeError(f"platform_admins.{email} no tiene totp_secret_encrypted -- falta un primer intento de login.")
    return totp_utils.decrypt_secret(row[0])


def platform_admin_login(api) -> str:
    """2FA es obligatorio para platform_admin (Grupo A) -- este helper hace
    el flujo completo (login -> setup u code_required -> confirm/verify),
    leyendo el secreto TOTP directo de salvio_control (mismo cifrado que usa
    el backend real, via app.utils.totp) en vez de mockear el 2FA."""
    resp = api.post(f"{BASE_URL}/api/v1/platform-admin/login", json={"email": PLATFORM_ADMIN_EMAIL, "password": PLATFORM_ADMIN_PASSWORD})
    resp.raise_for_status()
    data = resp.json()

    if data["status"] == "setup_required":
        secret = _platform_admin_totp_secret(PLATFORM_ADMIN_EMAIL)
        code = pyotp.TOTP(secret).now()
        confirm = api.post(
            f"{BASE_URL}/api/v1/platform-admin/2fa/setup/confirm",
            json={"code": code},
            headers=auth_headers(data["setup_token"]),
        )
        confirm.raise_for_status()
        return confirm.json()["access_token"]

    if data["status"] == "code_required":
        secret = _platform_admin_totp_secret(PLATFORM_ADMIN_EMAIL)
        code = pyotp.TOTP(secret).now()
        verify = api.post(
            f"{BASE_URL}/api/v1/platform-admin/2fa/verify",
            json={"code": code},
            headers=auth_headers(data["pending_token"]),
        )
        verify.raise_for_status()
        return verify.json()["access_token"]

    raise RuntimeError(f"Respuesta de login inesperada de platform-admin: {data}")


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def set_tenant_active(api, platform_token: str, tenant_id: str, is_active: bool) -> None:
    resp = api.patch(
        f"{BASE_URL}/api/v1/tenants/{tenant_id}",
        json={"is_active": is_active},
        headers=auth_headers(platform_token),
    )
    resp.raise_for_status()
