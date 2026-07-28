import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.models.tenant import OtpTokenSms, RevokedToken, User
from app.services._utils import commit_or_409, new_uuid_bytes
from app.utils.password import normalize_password, pwd_context

SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY") or "salvio-dev-secret-change-me"
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if not user:
        return None
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive.")
    try:
        valid = pwd_context.verify(normalize_password(password), user.hashed_password)
    except Exception:
        valid = normalize_password(password) == user.hashed_password
    return user if valid else None


def _user_uuid(user: User) -> str:
    return str(UUID(bytes=user.id)) if isinstance(user.id, (bytes, bytearray)) else str(user.id)


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": _user_uuid(user),
        "tenant_id": user.tenant_id,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "jti": str(uuid4()),
        "type": "access",
        "exp": now + timedelta(minutes=30),
        "iat": now,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": _user_uuid(user),
        "tenant_id": user.tenant_id,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "jti": str(uuid4()),
        "type": "refresh",
        "exp": now + timedelta(days=7),
        "iat": now,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str, db: Session) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.") from exc
    jti = payload.get("jti")
    if jti and db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked.")
    return payload


def revoke_token(db: Session, jti: str, user_id: bytes, expires_at: datetime) -> None:
    db.add(RevokedToken(id=new_uuid_bytes(), jti=jti, user_id=user_id, expires_at=expires_at))
    commit_or_409(db)


def verify_totp(secret: str, code: str) -> bool:
    try:
        import pyotp
    except Exception:
        return False
    return bool(pyotp.TOTP(secret).verify(code, valid_window=1))


def verify_otp_sms(db: Session, user_id: bytes, code: str) -> bool:
    token = (
        db.query(OtpTokenSms)
        .filter(
            OtpTokenSms.user_id == user_id,
            OtpTokenSms.used.is_(False),
            OtpTokenSms.expires_at > datetime.now(timezone.utc),
        )
        .order_by(OtpTokenSms.created_at.desc())
        .first()
    )
    if not token:
        return False
    valid = pwd_context.verify(normalize_password(code), token.otp_code_hash) if token.otp_code_hash else False
    if valid:
        token.used = True
        commit_or_409(db)
    return valid
