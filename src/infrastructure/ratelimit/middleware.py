"""
Production rate limiting middleware.

FastAPI/Starlette middleware that integrates the RateLimiter
with proper headers, exempt paths, and per-endpoint configuration.
"""

import time
from typing import Any, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.infrastructure.ratelimit.limiter import RateLimiter, RateLimitConfig

logger = structlog.get_logger(__name__)

# Endpoints that bypass rate limiting
DEFAULT_EXEMPT_PATHS: list[str] = [
    "/api/v1/health",
    "/docs",
    "/openapi.json",
    "/redoc",
]


class ProductionRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Production rate limiting middleware.

    Features:
    - Per-endpoint and per-role limits
    - Rate limit headers (X-RateLimit-*)
    - Configurable exempt paths
    - Redis-backed distributed limiting
    - Graceful degradation
    """

    def __init__(
        self,
        app: Callable,
        rate_limiter: RateLimiter | None = None,
        exempt_paths: list[str] | None = None,
        add_headers: bool = True,
    ) -> None:
        super().__init__(app)
        self._rate_limiter = rate_limiter
        self._exempt_paths = exempt_paths or DEFAULT_EXEMPT_PATHS
        self._add_headers = add_headers

    def _get_client_key(self, request: Request) -> str:
        """Derive rate limit key from request."""
        # Prefer validated API key
        api_key = getattr(request.state, "api_key", None)
        if api_key:
            return f"key:{api_key}"

        # Fall back to client IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"

    def _get_user_role(self, request: Request) -> str | None:
        """Extract user role from request state."""
        return getattr(request.state, "role", None)

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from rate limiting."""
        return any(path.startswith(exempt) for exempt in self._exempt_paths)

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        path = request.url.path

        # Skip exempt endpoints
        if self._is_exempt(path):
            return await call_next(request)

        # Skip if no rate limiter configured
        if self._rate_limiter is None:
            return await call_next(request)

        client_key = self._get_client_key(request)
        role = self._get_user_role(request)

        # Check rate limit
        result = await self._rate_limiter.check(
            key=client_key,
            path=path,
            role=role,
        )

        if not result.allowed:
            logger.warning(
                "rate_limit.exceeded",
                client_key=client_key,
                path=path,
                role=role,
                limit=result.limit,
                retry_after=result.retry_after,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "تم تجاوز حد الطلبات. يرجى المحاولة لاحقاً.",
                        "message_en": "Rate limit exceeded. Please retry later.",
                        "limit": result.limit,
                        "remaining": result.remaining,
                        "retry_after_seconds": int(result.retry_after) + 1,
                        "reset_at": int(result.reset_at),
                    }
                },
                headers=result.headers,
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        if self._add_headers:
            for header, value in result.headers.items():
                response.headers[header] = value

        return response
