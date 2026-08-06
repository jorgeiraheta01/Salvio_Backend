"""2FA (TOTP) para platform_admin -- unica cuenta con este nivel de acceso,
por eso es obligatorio (H-15 documenta por que NO se prioriza para usuarios
de clinica, pero el owner puede tumbar toda la plataforma: aca si aplica).
"""

import base64
import hashlib
import io
import os
import secrets
from typing import Iterable

import pyotp
import qrcode
from cryptography.fernet import Fernet, InvalidToken

ISSUER = "Salvio"


def _fernet() -> Fernet:
    # TOTP_ENCRYPTION_KEY en .env es un string cualquiera, no necesariamente
    # una clave Fernet valida (32 bytes url-safe base64) -- se deriva una
    # clave valida con SHA-256, determinista para el mismo valor de env.
    # Leido en el momento de uso (no a nivel de modulo) para que los tests
    # puedan correr aunque la env var no este seteada hasta el arranque real.
    raw_key = os.getenv("TOTP_ENCRYPTION_KEY")
    if not raw_key:
        raise RuntimeError(
            "TOTP_ENCRYPTION_KEY environment variable is not set. "
            "Refusing to encrypt/decrypt platform-admin TOTP secrets with an insecure default key."
        )
    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def generate_secret() -> str:
    return pyotp.random_base32()


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("No se pudo desencriptar el secreto TOTP -- TOTP_ENCRYPTION_KEY pudo haber cambiado.") from exc


def verify_code(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def provisioning_qr_png_base64(secret: str, account_email: str) -> str:
    uri = pyotp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=ISSUER)
    img = qrcode.make(uri)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def generate_recovery_codes(count: int = 10) -> list[str]:
    # Formato legible tipo "XXXX-XXXX", facil de transcribir a mano.
    return [f"{secrets.token_hex(4).upper()[:4]}-{secrets.token_hex(4).upper()[:4]}" for _ in range(count)]


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()


def code_matches_any(code: str, hashed_candidates: Iterable[str]) -> str | None:
    """Devuelve el hash que coincidio, o None. Comparacion por hash, nunca
    en texto plano ni almacenado en texto plano."""
    target = hash_recovery_code(code)
    for candidate in hashed_candidates:
        if secrets.compare_digest(target, candidate):
            return candidate
    return None
