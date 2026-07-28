from sqlalchemy.orm import sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.database import get_control_engine
from app.dependencies.auth import decode_token
from app.services.platform_settings_service import get_maintenance_mode


class MaintenanceModeMiddleware(BaseHTTPMiddleware):
    """Corta toda la API con 503 cuando el owner activa mantenimiento --
    excepto para el propio owner (JWT type=platform_admin), que nunca debe
    quedar fuera de su propia plataforma. Los tokens de 2FA (setup/pending)
    NO cuentan como platform_admin: no otorgan acceso real a la API."""

    async def dispatch(self, request: Request, call_next) -> Response:
        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())
        db = session_factory()
        try:
            state = get_maintenance_mode(db)
            enabled, message = state.enabled, state.message
        except Exception:
            # Si maintenance_mode todavia no existe (migracion control no
            # aplicada) no se debe tumbar toda la API -- se asume apagado.
            enabled, message = False, None
        finally:
            db.close()

        if not enabled:
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:]
            try:
                payload = decode_token(token)
                if payload.get("type") == "platform_admin":
                    return await call_next(request)
            except Exception:
                pass

        return JSONResponse(status_code=503, content={"detail": message or "Service under maintenance."})
