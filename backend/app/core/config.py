"""Application configuration.

All values are read from environment variables (and an optional ``.env`` file).
Never hard-code secrets; see ``.env.example`` for the documented set of keys.
"""
from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Medical Billing Coder"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"

    # Auth / token settings.
    secret_key: str = "dev-only-insecure-secret-change-me"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    jwt_algorithm: str = "HS256"

    # Database URL (SQLite for tests, PostgreSQL for production).
    database_url: str = "sqlite:///./mbc_dev.db"

    # MFA encryption (Fernet key) and audit HMAC key, kept separate from SECRET_KEY.
    mfa_encryption_key: str = ""
    audit_hmac_key: str = "dev-only-audit-hmac-change-me"

    # CORS / cookie settings.
    cors_origins: list[str] = ["http://localhost:3000"]
    cookie_secure: bool = False
    cookie_domain: str | None = None

    # Rate limiting.
    rate_limit_enabled: bool = True
    rate_limit_default: str = "100/minute"
    rate_limit_auth: str = "10/minute"
    rate_limit_trust_proxy: bool = False

    # AI provider. Transmission is OFF unless ai_enabled AND (for PHI-transmitting
    # providers) ai_phi_approved are both true. The mock provider is local-only.
    ai_enabled: bool = False
    ai_provider: str = "mock"
    ai_phi_approved: bool = False
    ai_timeout_seconds: float = 60.0
    ai_max_retries: int = 2
    ai_max_tokens: int = 4096
    ai_temperature: float = 0.0
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("cookie_domain", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @model_validator(mode="after")
    def _validate_ai_config(self) -> "Settings":
        if self.ai_enabled and self.ai_provider == "deepseek" and not self.deepseek_api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY is required when AI is enabled with the DeepSeek provider."
            )
        return self

    @model_validator(mode="after")
    def _reject_insecure_secrets_in_production(self) -> "Settings":
        if self.app_env == "production":
            if self.secret_key.startswith("dev-only") or self.audit_hmac_key.startswith("dev-only"):
                raise ValueError(
                    "Production mode requires SECRET_KEY and AUDIT_HMAC_KEY to be set "
                    "to real values (not the dev-only placeholders)."
                )
        return self

    @property
    def ai_transmission_enabled(self) -> bool:
        """True only when the global AI switch is on. The PHI approval gate is checked
        separately per-provider in the coding workflow (local mock needs no gate)."""
        return self.ai_enabled

    @property
    def is_testing(self) -> bool:
        return self.app_env == "testing"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance. Call ``get_settings.cache_clear()`` in
    tests that need to change configuration after the first import."""
    return Settings()
