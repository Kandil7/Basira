"""
API dependencies — dependency injection for FastAPI.
"""

from typing import Any

import structlog
from fastapi import HTTPException, Request

logger = structlog.get_logger(__name__)


def get_settings(request: Request) -> Any:
    """Get application settings from request state."""
    return request.app.state.settings


def get_analytics_service(request: Request) -> Any:
    """Get analytics service from request state."""
    return request.app.state.analytics_service


def get_customer_service(request: Request) -> Any:
    """Get customer service from request state."""
    return request.app.state.customer_service


def get_document_service(request: Request) -> Any:
    """Get document service from request state."""
    return request.app.state.document_service


def get_compiled_graph(request: Request) -> Any:
    """Get compiled LangGraph from request state."""
    return request.app.state.compiled_graph


def get_current_user(request: Request) -> str:
    """
    Extract the authenticated API key from the request.

    The auth middleware stores the validated key on request.state.api_key.
    Use this dependency in route handlers that need to know which client
    is making the request (e.g. for per-client logging or access control).

    Returns:
        The validated API key string.

    Raises:
        HTTPException: 401 if the request hasn't passed authentication.
    """
    api_key: str | None = getattr(request.state, "api_key", None)

    if not api_key:
        logger.warning("dependencies.get_current_user.no_key", path=request.url.path)
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "NOT_AUTHENTICATED",
                    "message": "Request has not been authenticated",
                }
            },
        )

    return api_key
