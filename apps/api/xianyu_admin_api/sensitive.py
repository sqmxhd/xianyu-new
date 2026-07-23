"""Small encryption boundary for short-lived platform verification data."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from .settings import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(
        f"xianyu-im-verification:{settings.jwt_secret}".encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_sensitive(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    return _fernet().encrypt(normalized.encode("utf-8")).decode("ascii")


def decrypt_sensitive(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    try:
        return _fernet().decrypt(normalized.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError):
        return None
