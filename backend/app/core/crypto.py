"""MFA secret encryption.

TOTP secrets are encrypted at rest with Fernet (AES-128-CBC + HMAC) using a key
provided via ``MFA_ENCRYPTION_KEY``. The raw secret is never stored in the
database and never logged. Key rotation requires re-encrypting stored secrets
with the new key; see docs/SECURITY.md.
"""
from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings


class MfaEncryptionError(RuntimeError):
    """Raised when MFA encryption is misconfigured or a secret cannot be decrypted."""


def _get_fernet() -> Fernet:
    key = get_settings().mfa_encryption_key
    if not key:
        raise MfaEncryptionError(
            "MFA_ENCRYPTION_KEY is not configured; MFA enrollment is disabled."
        )
    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - normalize Fernet's value errors
        raise MfaEncryptionError("MFA_ENCRYPTION_KEY is not a valid Fernet key.") from exc


def encrypt_mfa_secret(plaintext: str) -> str:
    """Encrypt a TOTP secret for storage."""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_mfa_secret(ciphertext: str) -> str:
    """Decrypt a stored TOTP secret. Raises ``MfaEncryptionError`` on key mismatch."""
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise MfaEncryptionError(
            "Stored MFA secret could not be decrypted (key mismatch or rotation)."
        ) from exc
