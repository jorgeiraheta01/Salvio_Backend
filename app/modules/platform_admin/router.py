from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.orm import sessionmaker

from app.core.rate_limit import limiter
from app.database import get_control_engine
from app.dependencies.auth import ALGORITHM, SECRET_KEY, decode_token, verify_password
from app.dependencies.platform_auth import (
    get_current_platform_admin,
    get_platform_admin_2fa_pending,
    get_platform_admin_2fa_setup,
    get_platform_admin_credentials,
)
from app.models.platform_admin import ControlRecoveryCode, ControlRevokedToken, PlatformAdmin
from app.schemas.common import MessageResponse
from app.utils import totp as totp_utils
from app.utils.control_audit import log_control_audit

router = APIRouter(prefix="/api/v1/platform-admin", tags=["Platform Admin"])

PLATFORM_ADMIN_TOKEN_EXPIRE_HOURS = 8
PLATFORM_ADMIN_2FA_SETUP_TOKEN_EXPIRE_MINUTES = 10
PLATFORM_ADMIN_2FA_PENDING_TOKEN_EXPIRE_MINUTES = 5
RECOVERY_CODE_COUNT = 10


class PlatformAdminLoginRequest(BaseModel):
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: SecretStr = Field(min_length=1, max_length=128)


class PlatformAdminLoginResponse(BaseModel):
    # 2FA es obligatorio para esta cuenta (Grupo A de la auditoria): un login
    # con credenciales validas nunca entrega un access_token completo por si
    # solo. "status" distingue los 3 desenlaces posibles de POST /login.
    status: str  # "setup_required" | "code_required"
    setup_token: str | None = None
    pending_token: str | None = None


class PlatformAdminAccessTokenResponse(BaseModel):
    access_token: str


class TotpSetupResponse(BaseModel):
    secret: str
    qr_base64: str


class TotpCodeRequest(BaseModel):
    code: str = Field(min_length=4, max_length=16)


class TotpSetupConfirmResponse(BaseModel):
    access_token: str
    recovery_codes: list[str]


def _issue_scoped_token(admin_id: str, token_type: str, expires_minutes: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {
        "sub": admin_id,
        "type": token_type,
        "exp": expires_at,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _issue_access_token(admin_id: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=PLATFORM_ADMIN_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": admin_id,
        "type": "platform_admin",
        "exp": expires_at,
        # uuid4, no timestamp con resolucion de segundo -- dos logins del
        # mismo admin dentro del mismo segundo antes generaban el mismo jti,
        # asi que revocar uno (logout) revocaba el otro token tambien.
        "jti": f"{admin_id}:platform_admin:{uuid4()}",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/login", response_model=PlatformAdminLoginResponse)
@limiter.limit("5/minute")
def platform_admin_login(request: Request, data: PlatformAdminLoginRequest) -> PlatformAdminLoginResponse:
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())
    db = session_factory()
    try:
        admin = db.query(PlatformAdmin).filter(PlatformAdmin.email == data.email.strip().lower()).first()
        if not admin or not admin.is_active or not verify_password(data.password.get_secret_value(), admin.hashed_password):
            # Tambien se audita el intento fallido -- login del owner es una
            # cuenta de alto impacto, sus intentos fallidos importan tanto
            # como sus exitos.
            log_control_audit(
                db,
                admin_id=admin.id if admin else None,
                action="login_failed",
                table_name="platform_admins",
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                new_values={"email": data.email.strip().lower()},
            )
            db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas.")

        admin_id = str(UUID(bytes=admin.id))

        if not admin.totp_confirmed_at:
            # Primer login o 2FA nunca terminado de confirmar -- flujo de
            # activacion obligatoria, no se entrega acceso real todavia.
            if not admin.totp_secret_encrypted:
                admin.totp_secret_encrypted = totp_utils.encrypt_secret(totp_utils.generate_secret())
            log_control_audit(
                db,
                admin_id=admin.id,
                action="login_2fa_setup_required",
                table_name="platform_admins",
                record_id=admin.id,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            db.commit()
            setup_token = _issue_scoped_token(admin_id, "platform_admin_2fa_setup", PLATFORM_ADMIN_2FA_SETUP_TOKEN_EXPIRE_MINUTES)
            return PlatformAdminLoginResponse(status="setup_required", setup_token=setup_token)

        log_control_audit(
            db,
            admin_id=admin.id,
            action="login_2fa_pending",
            table_name="platform_admins",
            record_id=admin.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        pending_token = _issue_scoped_token(admin_id, "platform_admin_2fa_pending", PLATFORM_ADMIN_2FA_PENDING_TOKEN_EXPIRE_MINUTES)
        return PlatformAdminLoginResponse(status="code_required", pending_token=pending_token)
    finally:
        db.close()


@router.get("/2fa/setup", response_model=TotpSetupResponse)
def platform_admin_2fa_setup(current_admin: PlatformAdmin = Depends(get_platform_admin_2fa_setup)) -> TotpSetupResponse:
    secret = totp_utils.decrypt_secret(current_admin.totp_secret_encrypted)
    return TotpSetupResponse(secret=secret, qr_base64=totp_utils.provisioning_qr_png_base64(secret, current_admin.email))


@router.post("/2fa/setup/confirm", response_model=TotpSetupConfirmResponse)
def platform_admin_2fa_setup_confirm(
    data: TotpCodeRequest,
    request: Request,
    current_admin: PlatformAdmin = Depends(get_platform_admin_2fa_setup),
) -> TotpSetupConfirmResponse:
    secret = totp_utils.decrypt_secret(current_admin.totp_secret_encrypted)
    if not totp_utils.verify_code(secret, data.code.strip()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Codigo invalido.")

    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())
    db = session_factory()
    try:
        admin = db.query(PlatformAdmin).filter(PlatformAdmin.id == current_admin.id).first()
        admin.totp_confirmed_at = datetime.now(timezone.utc)

        plain_codes = totp_utils.generate_recovery_codes(RECOVERY_CODE_COUNT)
        for code in plain_codes:
            db.add(ControlRecoveryCode(id=uuid4().bytes, admin_id=admin.id, code_hash=totp_utils.hash_recovery_code(code)))

        log_control_audit(
            db,
            admin_id=admin.id,
            action="2fa_enabled",
            table_name="platform_admins",
            record_id=admin.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        admin_id = str(UUID(bytes=admin.id))
        log_control_audit(
            db,
            admin_id=admin.id,
            action="login",
            table_name="platform_admins",
            record_id=admin.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        return TotpSetupConfirmResponse(access_token=_issue_access_token(admin_id), recovery_codes=plain_codes)
    finally:
        db.close()


@router.post("/2fa/verify", response_model=PlatformAdminAccessTokenResponse)
@limiter.limit("5/minute")
def platform_admin_2fa_verify(
    request: Request,
    data: TotpCodeRequest,
    current_admin: PlatformAdmin = Depends(get_platform_admin_2fa_pending),
) -> PlatformAdminAccessTokenResponse:
    code = data.code.strip()
    secret = totp_utils.decrypt_secret(current_admin.totp_secret_encrypted)
    admin_id = str(UUID(bytes=current_admin.id))

    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())
    db = session_factory()
    try:
        if totp_utils.verify_code(secret, code):
            log_control_audit(
                db,
                admin_id=current_admin.id,
                action="login",
                table_name="platform_admins",
                record_id=current_admin.id,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            db.commit()
            return PlatformAdminAccessTokenResponse(access_token=_issue_access_token(admin_id))

        # No fue un TOTP valido -- probar como codigo de recuperacion de un
        # solo uso antes de rechazar (dispositivo perdido es el caso de uso).
        unused = (
            db.query(ControlRecoveryCode)
            .filter(ControlRecoveryCode.admin_id == current_admin.id, ControlRecoveryCode.used_at.is_(None))
            .all()
        )
        matched_hash = totp_utils.code_matches_any(code, (row.code_hash for row in unused))
        if matched_hash:
            row = next(r for r in unused if r.code_hash == matched_hash)
            row.used_at = datetime.now(timezone.utc)
            log_control_audit(
                db,
                admin_id=current_admin.id,
                action="2fa_recovery_code_used",
                table_name="platform_admins",
                record_id=current_admin.id,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            log_control_audit(
                db,
                admin_id=current_admin.id,
                action="login",
                table_name="platform_admins",
                record_id=current_admin.id,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            db.commit()
            return PlatformAdminAccessTokenResponse(access_token=_issue_access_token(admin_id))

        log_control_audit(
            db,
            admin_id=current_admin.id,
            action="login_failed",
            table_name="platform_admins",
            record_id=current_admin.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            new_values={"reason": "invalid_2fa_code"},
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Codigo invalido.")
    finally:
        db.close()


@router.post("/logout", response_model=MessageResponse)
def platform_admin_logout(
    request: Request,
    current_admin: PlatformAdmin = Depends(get_current_platform_admin),
    credentials: HTTPAuthorizationCredentials = Depends(get_platform_admin_credentials),
) -> MessageResponse:
    payload = decode_token(credentials.credentials)
    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El token no tiene jti.")

    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())
    db = session_factory()
    try:
        if not db.query(ControlRevokedToken).filter(ControlRevokedToken.jti == jti).first():
            db.add(
                ControlRevokedToken(
                    id=uuid4().bytes,
                    jti=jti,
                    admin_id=current_admin.id,
                    expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                )
            )
        log_control_audit(
            db,
            admin_id=current_admin.id,
            action="logout",
            table_name="platform_admins",
            record_id=current_admin.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        return MessageResponse(message="OK")
    finally:
        db.close()
