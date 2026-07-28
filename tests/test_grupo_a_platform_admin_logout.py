"""
Grupo A: el owner debe poder cerrar su propia sesion, y el token
revocado debe dejar de funcionar de inmediato (antes: no existia
POST /platform-admin/logout, un token de 8h era valido hasta que
expiraba por su cuenta sin forma de cortarlo).
"""

from conftest import BASE_URL, auth_headers, platform_admin_login


def test_logout_revokes_the_token_immediately(api):
    token = platform_admin_login(api)

    resp = api.get(f"{BASE_URL}/api/v1/tenants", headers=auth_headers(token))
    assert resp.status_code == 200

    resp = api.post(f"{BASE_URL}/api/v1/platform-admin/logout", headers=auth_headers(token))
    assert resp.status_code == 200

    resp = api.get(f"{BASE_URL}/api/v1/tenants", headers=auth_headers(token))
    assert resp.status_code == 401


def test_logout_without_token_is_rejected(api):
    resp = api.post(f"{BASE_URL}/api/v1/platform-admin/logout")
    assert resp.status_code in (401, 403)
