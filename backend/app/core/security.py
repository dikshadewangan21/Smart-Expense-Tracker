import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False


def create_access_token(user_id: int) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "type": "access", "iat": now,
               "exp": now + timedelta(minutes=s.access_token_minutes)}
    return jwt.encode(payload, s.require_secret(), algorithm="HS256")


def decode_access_token(token: str) -> int:
    s = get_settings()
    payload = jwt.decode(token, s.require_secret(), algorithms=["HS256"])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return int(payload["sub"])


def new_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, sha256_hash). Only the hash is stored."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
