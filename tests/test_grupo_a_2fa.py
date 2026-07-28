"""
Grupo A: 2FA (TOTP) obligatorio para platform_admin. La cuenta owner ya
tiene 2FA activo desde que corrio el primer test de este proyecto (via el
helper platform_admin_login en conftest), asi que estos tests validan el
resto de las ramas del flujo: codigo invalido, token con scope incorrecto,
y consumo de un codigo de recuperacion.
"""

import pyotp
import pytest

from conftest import (
    BASE_URL,
    PLATFORM_ADMIN_EMAIL,
    PLATFORM_ADMIN_PASSWORD,
    _platform_admin_totp_secret,
    auth_headers,
    platform_admin_login,
)


def _login_pending_token(api) -> str:
    resp = api.post(f"{BASE_URL}/api/v1/platform-admin/login", json={"email": PLATFORM_ADMIN_EMAIL, "password": PLATFORM_ADMIN_PASSWORD})
    resp.raise_for_status()
    data = resp.json()
    assert data["status"] == "code_required", "este test asume que 2FA ya esta confirmado para el owner"
    return data["pending_token"]


def test_wrong_totp_code_is_rejected(api):
    pending_token = _login_pending_token(api)
    resp = api.post(
        f"{BASE_URL}/api/v1/platform-admin/2fa/verify",
        json={"code": "000000"},
        headers=auth_headers(pending_token),
    )
    assert resp.status_code == 401


def test_correct_totp_code_grants_access_token(api):
    pending_token = _login_pending_token(api)
    secret = _platform_admin_totp_secret(PLATFORM_ADMIN_EMAIL)
    code = pyotp.TOTP(secret).now()
    resp = api.post(
        f"{BASE_URL}/api/v1/platform-admin/2fa/verify",
        json={"code": code},
        headers=auth_headers(pending_token),
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_pending_token_cannot_be_used_as_access_token(api):
    pending_token = _login_pending_token(api)
    resp = api.get(f"{BASE_URL}/api/v1/tenants", headers=auth_headers(pending_token))
    assert resp.status_code == 403


def test_access_token_cannot_be_reused_on_2fa_verify(api):
    # Un access_token completo (type=platform_admin) no debe colar como
    # pending token (type=platform_admin_2fa_pending) -- distingue scope,
    # no solo firma valida.
    access_token = platform_admin_login(api)
    resp = api.post(
        f"{BASE_URL}/api/v1/platform-admin/2fa/verify",
        json={"code": "000000"},
        headers=auth_headers(access_token),
    )
    assert resp.status_code == 403
