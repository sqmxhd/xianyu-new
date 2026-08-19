"""Password hashing and JWT helpers for the admin API."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from typing import Any

import jwt

from .settings import settings

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260_000
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return "$".join(
        [
            PASSWORD_ALGORITHM,
            str(PASSWORD_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt_raw, digest_raw = stored_hash.split("$", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        iterations = int(iterations_raw)
        salt = base64.b64decode(salt_raw.encode("ascii"))
        expected = base64.b64decode(digest_raw.encode("ascii"))
    except Exception:
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def create_access_token(
    *,
    user_id: str,
    username: str,
    role: str,
    session_id: str | None = None,
) -> tuple[str, int]:
    expires_in = settings.access_token_expires_minutes * 60
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "role": role,
        "token_type": "admin_access" if session_id else "internal_service",
        "iat": now,
        "exp": now + expires_in,
        "jti": secrets.token_hex(16),
    }
    if session_id:
        payload["sid"] = session_id
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM), expires_in


def verify_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload if isinstance(payload.get("sub"), str) else None


def access_token_error(token: str) -> str:
    """Classify an invalid access token without exposing signing details."""

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return "ACCESS_TOKEN_EXPIRED"
    except jwt.PyJWTError:
        return "ACCESS_TOKEN_INVALID"
    if not isinstance(payload.get("sub"), str):
        return "ACCESS_TOKEN_INVALID"
    return "ACCESS_TOKEN_INVALID"


def hash_admin_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_admin_session_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(48)
    return token, hash_admin_session_token(token)
