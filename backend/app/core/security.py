"""Password hashing, JWT access tokens, and opaque refresh tokens."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from .config import get_settings
from .errors import UnauthorizedError

_password_hasher = PasswordHasher()

ACCESS_TOKEN_TYPE = "access"


def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2id (via argon2-cffi defaults)."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return True when ``password`` matches ``password_hash``.

    Never raises for mismatched or malformed hashes.
    """
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError, ValueError):
        return False


def create_access_token(
    *,
    user_id: str,
    organization_id: str,
    roles: list[str],
    expires_delta: timedelta | None = None,
) -> str:
    """Issue a short-lived, signed JWT access token."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload = {
        "sub": user_id,
        "org_id": organization_id,
        "roles": roles,
        "jti": secrets.token_urlsafe(16),
        "iat": now,
        "exp": expire,
        "iss": settings.app_name,
        "type": ACCESS_TOKEN_TYPE,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Validate and decode an access token, raising ``UnauthorizedError`` on failure."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "org_id", "roles", "type", "exp", "iat"]},
        )
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid or expired access token") from exc
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise UnauthorizedError("Invalid token type")
    return payload


def generate_refresh_token() -> str:
    """Generate a high-entropy opaque refresh token (only its SHA-256 hash is stored)."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token for storage. The raw token is never persisted."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_refresh_cookie_params(refresh_token: str) -> dict:
    """Return ``response.set_cookie`` kwargs for the HttpOnly refresh-token cookie.

    ``SameSite=Strict`` is the primary CSRF defense for the cookie; the refresh
    endpoint additionally validates the ``Origin`` header (defense in depth).
    """
    settings = get_settings()
    return {
        "key": "refresh_token",
        "value": refresh_token,
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "strict",
        "path": f"{settings.api_v1_prefix}/auth",
        "max_age": settings.refresh_token_expire_days * 86400,
        "domain": settings.cookie_domain,
    }
