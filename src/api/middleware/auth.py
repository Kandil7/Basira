"""
Authentication middleware.

Validates the X-Internal-Key header for all API endpoints
except /api/v1/health.
"""

from typing import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = structlog.get_logger(__name__)

# Endpoints that bypass authentication
AUTH_EXEMPT_PATHS: list[str] = [
    "/api/v1/health",
]


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that validates the X-Internal-Key header."""

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        path = request.url.path

        # Skip auth for exempt endpoints
        if any(path.startswith(exempt) for exempt in AUTH_EXEMPT_PATHS):
            return await call_next(request)

        # Extract the API key from the header
        api_key = request.headers.get("X-Internal-Key")

        if not api_key:
            logger.warning("auth.missing_key", path=path)
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "MISSING_API_KEY",
                        "message": "Missing X-Internal-Key header",
                    }
                },
            )

        # Validate against the configured key
        expected_key = request.app.state.settings.internal_api_key

        if not expected_key or expected_key == "change-me":
            logger.error("auth.key_not_configured", path=path)
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "AUTH_NOT_CONFIGURED",
                        "message": "Server authentication not configured",
                    }
                },
            )

        if api_key != expected_key:
            logger.warning("auth.invalid_key", path=path)
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "INVALID_API_KEY",
                        "message": "Invalid API key",
                    }
                },
            )

        # Store the validated key on request state for downstream use
        request.state.api_key = api_key

        return await call_next(request)
