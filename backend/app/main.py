"""FastAPI application factory and global error handling."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .api.v1.router import api_router
from .core.config import get_settings
from .core.errors import AppError
from .core.logging import configure_logging
from .db.session import engine


def _error_response(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    """Normalized error contract. Never includes stack traces, SQL, or request bodies."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request.headers.get("x-request-id"),
            }
        },
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return _error_response(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        # Do not echo the (possibly sensitive) request body back to the client.
        return _error_response(request, 422, "validation_error", "Request validation failed")

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        # Safe exception handling: log a redacted, non-sensitive summary only.
        logging.getLogger("app.errors").error(
            "Unhandled %s at %s %s", type(exc).__name__, request.method, request.url.path
        )
        return _error_response(request, 500, "internal_error", "Internal server error")

    @app.get("/health/live", tags=["health"])
    def liveness():
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    def readiness():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return {"status": "ready"}

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
