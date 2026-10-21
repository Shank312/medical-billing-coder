"""TOTP MFA enrollment, verification, and disable."""
import pyotp
from sqlalchemy.orm import Session

from ..core.crypto import decrypt_mfa_secret, encrypt_mfa_secret
from ..core.time import utcnow
from ..core.errors import BadRequestError, ConflictError, UnauthorizedError
from ..core.security import verify_password
from ..models.mfa import MfaConfig
from ..models.user import User
from ..repositories.mfa import MfaRepository
from .audit import AuditService

_ISSUER = "Medical Billing Coder"


def _mfa_enabled(config: MfaConfig | None) -> bool:
    return bool(config and config.enabled)


def mfa_enabled(db: Session, user_id: str) -> bool:
    return _mfa_enabled(MfaRepository(db).get_for_user(user_id))


def verify_totp(db: Session, user_id: str, code: str) -> bool:
    """Verify a TOTP code for a user with a 1-step clock-drift window."""
    config = MfaRepository(db).get_for_user(user_id)
    if config is None:
        return False
    secret = decrypt_mfa_secret(config.secret_encrypted)
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def enroll(
    db: Session,
    *,
    user: User,
    organization_id: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, str]:
    """Start TOTP enrollment; returns ``(secret, otpauth_uri)`` shown exactly once."""
    repo = MfaRepository(db)
    config = repo.get_for_user(user.id)
    if _mfa_enabled(config):
        raise ConflictError("MFA is already enabled", code="mfa_already_enabled")

    secret = pyotp.random_base32()
    encrypted = encrypt_mfa_secret(secret)
    if config is None:
        repo.create(user_id=user.id, secret_encrypted=encrypted)
    else:
        config.secret_encrypted = encrypted
        config.enabled = False

    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=_ISSUER)
    AuditService.append(
        db,
        organization_id=organization_id,
        actor_user_id=user.id,
        action="mfa.enroll_started",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return secret, uri


def verify_and_enable(
    db: Session,
    *,
    user: User,
    organization_id: str,
    code: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    config = MfaRepository(db).get_for_user(user.id)
    if config is None:
        raise BadRequestError("MFA enrollment has not been started", code="mfa_not_started")
    if not verify_totp(db, user.id, code):
        raise UnauthorizedError("Invalid MFA code")

    config.enabled = True
    config.last_verified_at = utcnow()
    AuditService.append(
        db,
        organization_id=organization_id,
        actor_user_id=user.id,
        action="mfa.enabled",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def disable(
    db: Session,
    *,
    user: User,
    organization_id: str,
    password: str,
    code: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    if not verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid password")

    config = MfaRepository(db).get_for_user(user.id)
    if not _mfa_enabled(config):
        raise BadRequestError("MFA is not enabled", code="mfa_not_enabled")
    if not verify_totp(db, user.id, code):
        raise UnauthorizedError("Invalid MFA code")

    config.enabled = False
    config.secret_encrypted = ""
    config.last_verified_at = None
    AuditService.append(
        db,
        organization_id=organization_id,
        actor_user_id=user.id,
        action="mfa.disabled",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
