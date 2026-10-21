"""Rate limiting unit and integration tests."""
from app.core.config import Settings
from app.core.rate_limit import (
    SlidingWindowRateLimiter,
    parse_limit,
    reset_all_limiters,
)


def test_parse_limit():
    assert parse_limit("100/minute") == (100, 60)
    assert parse_limit("5/second") == (5, 1)


def test_sliding_window():
    limiter = SlidingWindowRateLimiter(2, 60)
    assert limiter.allow("key") is True
    assert limiter.allow("key") is True
    assert limiter.allow("key") is False


def test_rate_limit_http(client, monkeypatch):
    custom = Settings(rate_limit_enabled=True, rate_limit_auth="2/minute", rate_limit_trust_proxy=False)
    monkeypatch.setattr("app.core.rate_limit.get_settings", lambda: custom)
    reset_all_limiters()

    payload = {"email": "nobody@example.com", "password": "whatever-password"}
    for _ in range(2):
        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 401

    blocked = client.post("/api/v1/auth/login", json=payload)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    reset_all_limiters()
