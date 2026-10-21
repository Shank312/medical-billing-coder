"""Redacted, structured logging.

Passwords, tokens, MFA secrets, Authorization headers, and clinical text are
never written to logs. Log metadata by default, never log clinical notes.
"""
import logging
import re

REDACTED = "[REDACTED]"

_SENSITIVE_KEY_SET = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "authorization",
    "refresh_token",
    "access_token",
    "mfa_secret",
    "otp",
    "pin",
    "api_key",
    "apikey",
    "credential",
    "client_secret",
    "clinical_note",
    "note_text",
    "chart",
    "ssn",
    "dob",
}

# "key = value" / "key=value" / "key: value" patterns for string messages.
_KEY_VALUE_RE = re.compile(
    r"(?i)([\"\']?(?:password|passwd|pwd|secret|token|authorization|refresh_token|"
    r"access_token|mfa_secret|otp|pin|api_key|apikey|credential|client_secret|"
    r"clinical_note|note_text|chart|ssn|dob)[\"\']?\s*[:=]\s*)([^,\s}\]]+)"
)


def _is_sensitive_key(key: str) -> bool:
    normalized = str(key).lower()
    return normalized in _SENSITIVE_KEY_SET


def redact_text(text: str) -> str:
    """Redact sensitive key/value pairs found inside a flat string."""
    if not isinstance(text, str):
        return text
    return _KEY_VALUE_RE.sub(lambda match: match.group(1) + REDACTED, text)


def redact(value: object) -> object:
    """Recursively redact sensitive keys and string values in structured data."""
    if isinstance(value, dict):
        return {key: (REDACTED if _is_sensitive_key(str(key)) else redact(val)) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


class RedactingFilter(logging.Filter):
    """Logging filter that scrubs sensitive material from the record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = redact(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(redact(arg) for arg in record.args)
        return True


_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the root logger once with a redacting formatter."""
    global _configured
    if _configured:
        return
    root = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    _configured = True
