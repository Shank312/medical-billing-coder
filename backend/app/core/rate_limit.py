"""Shared, in-process sliding-window rate limiting.

The default store is process-local, which is correct only for a single-process
deployment. For a multi-worker production deployment this must be backed by a
shared store (e.g. Redis); the interface is intentionally small to allow that
swap. See docs/SECURITY.md.
"""
import threading
import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request

from .config import get_settings
from .errors import RateLimitError

_UNIT_SECONDS = {
    "second": 1,
    "seconds": 1,
    "s": 1,
    "minute": 60,
    "minutes": 60,
    "m": 60,
    "hour": 3600,
    "hours": 3600,
    "h": 3600,
    "day": 86400,
    "days": 86400,
    "d": 86400,
}


def parse_limit(limit: str) -> tuple[int, int]:
    """Parse a limit string such as ``100/minute`` into ``(count, window_seconds)``."""
    try:
        count_s, unit = limit.strip().split("/", 1)
        count = int(count_s)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid rate limit: {limit!r}") from exc
    seconds = _UNIT_SECONDS.get(unit.strip().lower())
    if seconds is None or count < 1:
        raise ValueError(f"Invalid rate limit: {limit!r}")
    return count, seconds


class SlidingWindowRateLimiter:
    """A thread-safe sliding-window limiter keyed by an arbitrary string."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            queue = self._hits[key]
            while queue and now - queue[0] >= self.window_seconds:
                queue.popleft()
            if len(queue) >= self.max_requests:
                return False
            queue.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_LIMITERS: dict[str, SlidingWindowRateLimiter] = {}
_LIMITERS_LOCK = threading.Lock()


def get_limiter(limit: str) -> SlidingWindowRateLimiter:
    count, seconds = parse_limit(limit)
    with _LIMITERS_LOCK:
        if limit not in _LIMITERS:
            _LIMITERS[limit] = SlidingWindowRateLimiter(count, seconds)
        return _LIMITERS[limit]


def reset_all_limiters() -> None:
    with _LIMITERS_LOCK:
        for limiter in _LIMITERS.values():
            limiter.reset()


def client_ip(request: Request, trust_proxy: bool) -> str:
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit_dependency(limit: str, *, key_prefix: str = "") -> Callable[[Request], None]:
    """Factory returning a FastAPI dependency that enforces a shared rate limit."""
    return configured_rate_limit_dependency(None, limit=limit, key_prefix=key_prefix)


def configured_rate_limit_dependency(
    settings_attr: str | None, *, limit: str | None = None, key_prefix: str = ""
) -> Callable[[Request], None]:
    """Factory returning a dependency that reads its limit from settings at request
    time (``settings_attr``) or uses a fixed ``limit`` string. Reading at request time
    keeps limits configurable and testable."""

    def _enforce(request: Request) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        resolved = getattr(settings, settings_attr) if settings_attr else limit
        if not resolved:
            return
        limiter = get_limiter(resolved)
        ip = client_ip(request, settings.rate_limit_trust_proxy)
        key = f"{key_prefix}:{ip}:{request.url.path}"
        if not limiter.allow(key):
            raise RateLimitError("Too many requests. Please retry later.")

    return _enforce
