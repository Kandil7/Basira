"""
Rate limiting middleware.

Simple in-memory sliding window rate limiter.
Tracks requests per API key (or IP if no key).
"""

import time
from collections import defaultdict
from typing import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = structlog.get_logger(__name__)

# Default rate limit: 60 requests per minute
DEFAULT_RATE_LIMIT = 60
DEFAULT_WINDOW_SECONDS = 60

# Endpoints that bypass rate limiting
RATE_LIMIT_EXEMPT_PATHS: list[str] = [
    "/api/v1/health",
]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces per-key sliding window rate limits."""

    def __init__(
        self,
        app: Callable,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        super().__init__(app)
        self.rate_limit = rate_limit
        self.window_seconds = window_seconds
        # {key: [(timestamp, count), ...]}
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_client_key(self, request: Request) -> str:
        """Derive a rate limit key from the request."""
        # Prefer the validated API key from auth middleware
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

    def _is_rate_limited(self, key: str) -> bool:
        """Check if the client has exceeded the rate limit."""
        now = time.monotonic()
        window_start = now - self.window_seconds

        # Prune old entries
        self._requests[key] = [
            ts for ts in self._requests[key] if ts > window_start
        ]

        if len(self._requests[key]) >= self.rate_limit:
            return True

        # Record this request
        self._requests[key].append(now)
        return False

    def _get_retry_after(self, key: str) -> int:
        """Calculate seconds until the oldest request in the window expires."""
        if not self._requests[key]:
            return 0
        oldest = self._requests[key][0]
        elapsed = time.monotonic() - oldest
        return max(1, int(self.window_seconds - elapsed) + 1)

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        path = request.url.path

        # Skip rate limiting for exempt endpoints
        if any(path.startswith(exempt) for exempt in RATE_LIMIT_EXEMPT_PATHS):
            return await call_next(request)

        client_key = self._get_client_key(request)

        if self._is_rate_limited(client_key):
            retry_after = self._get_retry_after(client_key)
            logger.warning(
                "rate_limit.exceeded",
                client_key=client_key,
                path=path,
                retry_after=retry_after,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please retry later.",
                        "retry_after_seconds": retry_after,
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
