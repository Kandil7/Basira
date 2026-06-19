"""
Health check endpoint.

Provides system health status for monitoring and n8n workflows.
Phase 2: Added response time measurement and detailed dependency status.
"""

import time
from typing import Any

from fastapi import APIRouter, Request
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> dict[str, Any]:
    """
    System health check.

    Returns status of all connected services (Qdrant, Odoo, LLM) with
    response time measurements.
    """
    services: dict[str, Any] = {}
    overall_start = time.time()

    # Check Qdrant
    try:
        qdrant_store = request.app.state.qdrant_store
        start = time.time()
        qdrant_ok = await qdrant_store.health_check()
        elapsed_ms = round((time.time() - start) * 1000, 1)
        services["qdrant"] = {
            "status": "connected" if qdrant_ok else "disconnected",
            "response_time_ms": elapsed_ms,
        }
    except Exception as e:
        services["qdrant"] = {"status": "error", "error": str(e)}

    # Check Odoo
    try:
        odoo_client = request.app.state.odoo_client
        start = time.time()
        odoo_ok = await odoo_client.health_check()
        elapsed_ms = round((time.time() - start) * 1000, 1)
        services["odoo"] = {
            "status": "connected" if odoo_ok else "disconnected",
            "response_time_ms": elapsed_ms,
        }
    except Exception as e:
        services["odoo"] = {"status": "error", "error": str(e)}

    # Check LLM
    try:
        settings = request.app.state.settings
        has_key = bool(settings.groq_api_key and settings.groq_api_key != "change-me")
        services["llm"] = {
            "status": "available" if has_key else "no_api_key",
            "model": settings.groq_model,
        }
    except Exception as e:
        services["llm"] = {"status": "error", "error": str(e)}

    total_ms = round((time.time() - overall_start) * 1000, 1)
    healthy_count = sum(
        1 for s in services.values()
        if isinstance(s, dict) and s.get("status") in ("connected", "available")
    )

    return {
        "status": "healthy" if healthy_count == len(services) else "degraded",
        "services": services,
        "healthy_count": healthy_count,
        "total_count": len(services),
        "response_time_ms": total_ms,
        "version": "0.1.0",
    }
