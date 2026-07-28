from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_control_engine
from app.dependencies.auth import decode_token
from app.models.platform_admin import ControlRevokedToken, PlatformAdmin

security = HTTPBearer(auto_error=True)


def get_current_platform_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> PlatformAdmin:
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "platform_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin access required.")

    admin_id = payload.get("sub")
    if not admin_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")

    jti = payload.get("jti")

    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())
    db: Session = session_factory()
    try:
        if jti and db.query(ControlRevokedToken).filter(ControlRevokedToken.jti == jti).first():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked.")
        admin = db.query(PlatformAdmin).filter(PlatformAdmin.id == UUID(admin_id).bytes).first()
    finally:
        db.close()

    if not admin or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Platform admin not found or inactive.")
    return admin


def get_platform_admin_credentials(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> HTTPAuthorizationCredentials:
    """Expone las credenciales crudas (para leer el jti) sin duplicar la
    validacion de get_current_platform_admin -- se usan juntas en /logout."""
    return credentials


def _admin_from_scoped_token(credentials: HTTPAuthorizationCredentials, expected_type: str) -> PlatformAdmin:
    """Para los tokens de corta duracion del flujo de 2FA (setup / pending),
    deliberadamente distintos de un token 'platform_admin' completo: no
    otorgan acceso a la API, solo permiten terminar el paso de 2FA que les
    corresponde. No se chequea revoked_tokens (nunca se emiten como
    access_token real, y su vida es de minutos)."""
    payload = decode_token(credentials.credentials)
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token scope.")

    admin_id = payload.get("sub")
    if not admin_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")

    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())
    db: Session = session_factory()
    try:
        admin = db.query(PlatformAdmin).filter(PlatformAdmin.id == UUID(admin_id).bytes).first()
    finally:
        db.close()

    if not admin or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Platform admin not found or inactive.")
    return admin


def get_platform_admin_2fa_setup(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> PlatformAdmin:
    return _admin_from_scoped_token(credentials, "platform_admin_2fa_setup")


def get_platform_admin_2fa_pending(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> PlatformAdmin:
    return _admin_from_scoped_token(credentials, "platform_admin_2fa_pending")
