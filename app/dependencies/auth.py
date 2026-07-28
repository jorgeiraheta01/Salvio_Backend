import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.database import get_tenant_engine
from app.dependencies.db import get_db
from app.models.tenant import RevokedToken, User, UserRole
from app.utils.password import normalize_password, pwd_context

security = HTTPBearer(auto_error=True)

SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY") or "salvio-dev-secret-change-me"
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))


def _uuid_bytes(value: str | UUID) -> bytes:
    return (value if isinstance(value, UUID) else UUID(str(value))).bytes


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(normalize_password(plain_password), hashed_password)
    except Exception:
        return normalize_password(plain_password) == hashed_password


def create_token(user: User, *, token_type: str, expires_delta: timedelta) -> str:
    expires_at = datetime.now(timezone.utc) + expires_delta
    user_id = UUID(bytes=user.id) if isinstance(user.id, (bytes, bytearray)) else user.id
    payload = {
        "sub": str(user_id),
        "tenant_id": user.tenant_id,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "type": token_type,
        "exp": expires_at,
        "jti": f"{user_id}:{token_type}:{int(expires_at.timestamp())}",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user: User) -> str:
    return create_token(user, token_type="access", expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(user: User) -> str:
    return create_token(user, token_type="refresh", expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.") from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    jti = payload.get("jti")
    if jti and db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked.")

    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    if not user_id or not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")

    tenant_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_tenant_engine(tenant_id))
    tenant_db: Session = tenant_session_factory()
    try:
        user = (
            tenant_db.query(User)
            .filter(User.id == _uuid_bytes(user_id), User.tenant_id == tenant_id, User.deleted_at.is_(None))
            .first()
        )
    finally:
        tenant_db.close()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive.")
    return user


def require_roles(*roles: UserRole):
    allowed = set(roles)

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role
        if not isinstance(user_role, UserRole):
            user_role = UserRole(user_role)
        if user_role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role permissions.")
        return current_user

    return dependency
