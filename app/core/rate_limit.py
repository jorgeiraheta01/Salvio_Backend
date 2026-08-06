"""Limitador de tasa compartido para endpoints sensibles a fuerza bruta
(login de clinica, login de owner, verificacion de 2FA del owner). Una
sola instancia de `Limiter` para toda la app -- slowapi requiere que el
`request: Request` este entre los parametros del endpoint decorado con
`@limiter.limit(...)` para poder leer la IP del cliente.

RATE_LIMIT_ENABLED (default "true") existe porque la suite de tests de este
proyecto pega contra el servidor real corriendo (no hay TestClient aislado,
ver tests/conftest.py), y llama a los endpoints de login decenas de veces
en el mismo minuto desde la misma IP -- con el limite prendido, la propia
suite se autobloquea. Mismo patron ya usado en el proyecto para
TENANT_2FA_ENABLED (app/routers/auth.py): apagado explicito via env var
para corridas de test, prendido por defecto en cualquier otro caso."""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"

limiter = Limiter(key_func=get_remote_address, enabled=RATE_LIMIT_ENABLED)
