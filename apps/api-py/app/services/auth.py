from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import AppUser, AuthSession


def hash_password(password: str, salt: str) -> str:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), n=16384, r=8, p=1, dklen=64).hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt), expected_hash)


def create_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticate_user(db: Session, email: str, password: str) -> dict | None:
    user = db.scalar(select(AppUser).where(AppUser.email == email, AppUser.status == "启用"))
    if not user or not user.password_hash or not user.password_salt:
        return None
    if not verify_password(password, user.password_salt, user.password_hash):
        return None

    token = create_session_token()
    session = AuthSession(
        token_hash=hash_token(token),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
    )
    db.add(session)
    db.commit()
    return {"token": token, "user": map_user(user)}


def get_session_user(db: Session, token: str | None) -> dict | None:
    if not token:
        return None
    user = db.scalar(
        select(AppUser)
        .join(AuthSession, AuthSession.user_id == AppUser.id)
        .where(AuthSession.token_hash == hash_token(token), AuthSession.expires_at > datetime.now(timezone.utc), AppUser.status == "启用")
    )
    return map_user(user) if user else None


def logout_session(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(token)))
        db.commit()


def map_user(user: AppUser) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "role": user.role,
        "department": user.department,
        "status": user.status,
        "email": user.email,
    }

