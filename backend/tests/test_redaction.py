"""Logging redaction tests."""
import io
import logging

from app.core.logging import RedactingFilter, redact, redact_text


def test_redact_text():
    assert redact_text("password=secret123") == "password=[REDACTED]"
    assert redact_text("token=abc123") == "token=[REDACTED]"


def test_redact_dict():
    output = redact(
        {
            "password": "pw",
            "token": "tk",
            "name": "alice",
            "nested": {"secret": "s", "public": "ok"},
        }
    )
    assert output["password"] == "[REDACTED]"
    assert output["token"] == "[REDACTED]"
    assert output["name"] == "alice"
    assert output["nested"]["secret"] == "[REDACTED]"
    assert output["nested"]["public"] == "ok"


def test_logging_filter_redacts():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger("redaction_capture_test")
    logger.handlers = []
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    logger.addFilter(RedactingFilter())

    logger.info("auth password=supersecret token=abc123 refresh_token=xyz")

    output = stream.getvalue()
    assert "supersecret" not in output
    assert "abc123" not in output
    assert "xyz" not in output
    assert "[REDACTED]" in output
