"""Application error contract.

All HTTP errors are raised as ``AppError`` subclasses and normalized to a single
JSON shape by the global exception handler in ``app.main``. Client responses
never include stack traces, SQL, or other internal detail.
"""


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str = "Internal error",
        *,
        code: str | None = None,
        status_code: int | None = None,
        detail: dict | None = None,
    ) -> None:
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.detail = detail or {}
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
