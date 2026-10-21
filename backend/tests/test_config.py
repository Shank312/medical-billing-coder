"""Configuration validation tests."""
import pytest

from app.core.config import Settings


def test_production_rejects_dev_secrets():
    with pytest.raises(ValueError):
        Settings(
            app_env="production",
            secret_key="dev-only-insecure-secret-change-me",
            audit_hmac_key="dev-only-audit-hmac-change-me",
        )


def test_production_accepts_real_secrets():
    settings = Settings(
        app_env="production",
        secret_key="a-real-32-plus-character-production-secret",
        audit_hmac_key="a-real-32-plus-character-audit-secret",
        mfa_encryption_key="a-real-fernet-key-material-here-32b=",
        cookie_secure=True,
    )
    assert settings.is_production is True
