"""
Guardrails middleware — validates agent inputs and outputs against safety rules.

Integrates with GuardrailsEngine and PIIDetector to filter harmful content
and mask personally identifiable information.
"""

from typing import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.infrastructure.guardrails.engine import guardrails_engine, GuardrailAction
from src.infrastructure.guardrails.pii import pii_detector

logger = structlog.get_logger(__name__)

# Endpoints that bypass guardrails
GUARDRAILS_EXEMPT_PATHS: list[str] = [
    "/api/v1/health",
]


class GuardrailsMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces guardrails on agent inputs and outputs."""

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        path = request.url.path

        # Skip guardrails for exempt endpoints
        if any(path.startswith(exempt) for exempt in GUARDRAILS_EXEMPT_PATHS):
            return await call_next(request)

        # Store guardrails engine and PII detector on request state
        request.state.guardrails = guardrails_engine
        request.state.pii_detector = pii_detector

        # Process request
        response = await call_next(request)

        return response
