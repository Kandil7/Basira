"""
RBAC middleware — validates user permissions for API endpoints.

Integrates with RBACMiddleware to enforce role-based access control.
"""

from typing import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.infrastructure.rbac import rbac, Role

logger = structlog.get_logger(__name__)

# Endpoints that bypass RBAC
RBAC_EXEMPT_PATHS: list[str] = [
    "/api/v1/health",
]


class RBACMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces RBAC on API endpoints."""

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        path = request.url.path

        # Skip RBAC for exempt endpoints
        if any(path.startswith(exempt) for exempt in RBAC_EXEMPT_PATHS):
            return await call_next(request)

        # Get user from request (set by auth middleware or header)
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            # Default to API role for unauthenticated requests
            user_id = "n8n"

        user = rbac.get_user(user_id)
        if not user:
            logger.warning("rbac.unknown_user", user_id=user_id, path=path)
            # Create a viewer user for unknown users
            from src.infrastructure.rbac import User
            user = User(user_id, Role.VIEWER, f"Unknown: {user_id}")

        # Store user on request state
        request.state.user = user
        request.state.rbac = rbac

        # Check endpoint access
        method = request.method
        if not rbac.check_endpoint_access(user, path, method):
            logger.warning(
                "rbac.access_denied",
                user=user_id,
                role=user.role.value,
                path=path,
                method=method,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": f"Insufficient permissions for {method} {path}",
                        "required_role": rbac._endpoint_permissions.get(
                            f"{method}:{path}", set()
                        ),
                    }
                },
            )

        return await call_next(request)
