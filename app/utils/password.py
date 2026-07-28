from __future__ import annotations

import bcrypt
from passlib.context import CryptContext


def _patch_bcrypt_for_passlib() -> None:
    if not hasattr(bcrypt, "__about__"):
        class _About:
            __version__ = getattr(bcrypt, "__version__", "")

        bcrypt.__about__ = _About()

    original_hashpw = getattr(bcrypt, "hashpw", None)
    if original_hashpw is None or getattr(original_hashpw, "_salvio_passlib_compat", False):
        return

    def _compat_hashpw(password: bytes, salt: bytes):
        try:
            return original_hashpw(password, salt)
        except ValueError as exc:
            if "longer than 72 bytes" in str(exc) and isinstance(password, (bytes, bytearray)):
                return original_hashpw(bytes(password)[:72], salt)
            raise

    _compat_hashpw._salvio_passlib_compat = True
    bcrypt.hashpw = _compat_hashpw


_patch_bcrypt_for_passlib()

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def normalize_password(password: object) -> str:
    return str(password).strip()
