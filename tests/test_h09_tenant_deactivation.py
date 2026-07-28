"""
H-09: bloquear una clinica debe cortar las sesiones ya emitidas de esa
clinica (access token y refresh token), no solo impedir logins nuevos.

Antes del fix: get_current_user() y refresh_token() solo validaban
User.is_active, nunca Tenant.is_active -- un usuario con un token ya
emitido seguia operando hasta que ese token expirara (hasta 60 min de
access, hasta 30 dias de refresh) aunque el owner hubiera bloqueado la
clinica en ese mismo instante.
"""

from conftest import (
    BASE_URL,
    QA_ADMIN_EMAIL,
    QA_PASSWORD,
    QA_TENANT,
    auth_headers,
    login,
    platform_admin_login,
    set_tenant_active,
)


def test_deactivating_tenant_cuts_active_access_token(api):
    tokens = login(api, QA_TENANT, QA_ADMIN_EMAIL, QA_PASSWORD)
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # sanity: el token funciona mientras la clinica esta activa
    resp = api.get(f"{BASE_URL}/api/v1/users", headers=auth_headers(access_token))
    assert resp.status_code == 200

    platform_token = platform_admin_login(api)
    try:
        set_tenant_active(api, platform_token, QA_TENANT, is_active=False)

        # el MISMO access token, emitido antes del bloqueo, ya no debe funcionar
        resp = api.get(f"{BASE_URL}/api/v1/users", headers=auth_headers(access_token))
        assert resp.status_code == 403, f"esperaba 403 con la clinica bloqueada, obtuve {resp.status_code}"

        # tampoco debe poder renovarse via refresh
        resp = api.post(f"{BASE_URL}/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 403, f"esperaba 403 al renovar con la clinica bloqueada, obtuve {resp.status_code}"

        # el login mismo tambien debe seguir bloqueado (comportamiento previo, no debe regresionar)
        resp = api.post(f"{BASE_URL}/api/v1/auth/login", json={"tenant_id": QA_TENANT, "email": QA_ADMIN_EMAIL, "password": QA_PASSWORD})
        assert resp.status_code == 403
    finally:
        # siempre reactivar, incluso si una asercion fallo -- es una clinica de QA compartida
        set_tenant_active(api, platform_token, QA_TENANT, is_active=True)

    # sanity final: reactivada la clinica, un login nuevo si funciona
    tokens_after = login(api, QA_TENANT, QA_ADMIN_EMAIL, QA_PASSWORD)
    resp = api.get(f"{BASE_URL}/api/v1/users", headers=auth_headers(tokens_after["access_token"]))
    assert resp.status_code == 200
