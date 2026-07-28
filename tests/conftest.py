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

import pytest
import requests

BASE_URL = "http://127.0.0.1:8000"
QA_TENANT = "clinica_qa_norte"
QA_ADMIN_EMAIL = "admin@qanorte.dev"
QA_DOCTOR_EMAIL = "iportillo@qanorte.dev"
QA_PASSWORD = "Test1234!"
PLATFORM_ADMIN_EMAIL = "owner@salvio.dev"
PLATFORM_ADMIN_PASSWORD = "SalvioOwner2026!"


@pytest.fixture(scope="session")
def api():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def login(api, tenant_id: str, email: str, password: str) -> dict:
    resp = api.post(f"{BASE_URL}/api/v1/auth/login", json={"tenant_id": tenant_id, "email": email, "password": password})
    resp.raise_for_status()
    return resp.json()


def platform_admin_login(api) -> str:
    resp = api.post(f"{BASE_URL}/api/v1/platform-admin/login", json={"email": PLATFORM_ADMIN_EMAIL, "password": PLATFORM_ADMIN_PASSWORD})
    resp.raise_for_status()
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def set_tenant_active(api, platform_token: str, tenant_id: str, is_active: bool) -> None:
    resp = api.patch(
        f"{BASE_URL}/api/v1/tenants/{tenant_id}",
        json={"is_active": is_active},
        headers=auth_headers(platform_token),
    )
    resp.raise_for_status()
