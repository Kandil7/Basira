"""
Webhook receiver — FastAPI endpoint for Odoo webhook events.
"""

import time
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from src.infrastructure.webhooks.models import WebhookEvent
from src.infrastructure.webhooks.parser import WebhookPayloadParser
from src.infrastructure.webhooks.security import WebhookSecurity

logger = structlog.get_logger(__name__)

router = APIRouter()


class WebhookResponse(BaseModel):
    """Response for webhook events."""
    success: bool
    event_id: str | None = None
    message: str
    processing_time_ms: float = 0


class WebhookHealthResponse(BaseModel):
    """Webhook system health."""
    status: str
    events_received: int
    events_processed: int
    events_failed: int
    avg_processing_time_ms: float


# Global parser (shared across requests)
_parser = WebhookPayloadParser()


@router.post("/webhooks/odoo")
async def receive_odoo_webhook(
    request: Request,
    x_odoo_signature: str | None = None,
    x_odoo_timestamp: str | None = None,
    x_odoo_event_id: str | None = None,
) -> WebhookResponse:
    """
    Receive webhook events from Odoo.

    Headers:
    - X-Odoo-Signature: HMAC signature for validation
    - X-Odoo-Timestamp: Request timestamp
    - X-Odoo-Event-ID: Unique event identifier

    Body: Odoo webhook payload (JSON)
    """
    start = time.time()

    try:
        # Read request body
        body = await request.body()

        # Validate signature if security is configured
        security: WebhookSecurity | None = getattr(request.app.state, "webhook_security", None)
        if security and x_odoo_signature:
            if not security.validate_signature(body, x_odoo_signature, x_odoo_timestamp):
                raise HTTPException(status_code=401, detail="Invalid webhook signature")

        # Check client IP if whitelist configured
        client_ip = request.client.host if request.client else "unknown"
        if security and not security.check_ip_whitelist(client_ip):
            raise HTTPException(status_code=403, detail="IP not allowed")

        # Parse payload
        import json
        payload = json.loads(body)

        # Parse event
        event = _parser.parse_event(payload)

        # Process event through sync service
        sync_service = getattr(request.app.state, "inventory_sync", None)
        if sync_service:
            await sync_service.process_event(event)

        processing_time = (time.time() - start) * 1000

        logger.info(
            "webhook.received",
            event_id=event.event_id,
            event_type=event.event_type.value,
            processing_time_ms=round(processing_time, 2),
        )

        return WebhookResponse(
            success=True,
            event_id=event.event_id,
            message=f"Event {event.event_type.value} processed successfully",
            processing_time_ms=round(processing_time, 2),
        )

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        processing_time = (time.time() - start) * 1000
        logger.error(
            "webhook.processing_failed",
            error=str(e),
            processing_time_ms=round(processing_time, 2),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhooks/odoo/test")
async def test_webhook(
    payload: dict[str, Any] = None,
) -> WebhookResponse:
    """
    Test webhook endpoint — validates webhook configuration.
    """
    start = time.time()

    if payload is None:
        payload = {"model": "test", "action": "test"}

    event = _parser.parse_event(payload)
    processing_time = (time.time() - start) * 1000

    return WebhookResponse(
        success=True,
        event_id=event.event_id,
        message="Test webhook received successfully",
        processing_time_ms=round(processing_time, 2),
    )


@router.get("/webhooks/health")
async def webhook_health(request: Request) -> WebhookHealthResponse:
    """Check webhook system health."""
    sync_service = getattr(request.app.state, "inventory_sync", None)

    if sync_service:
        stats = sync_service.get_stats()
        return WebhookHealthResponse(
            status="healthy",
            events_received=stats.get("events_received", 0),
            events_processed=stats.get("events_processed", 0),
            events_failed=stats.get("events_failed", 0),
            avg_processing_time_ms=stats.get("avg_processing_time_ms", 0),
        )

    return WebhookHealthResponse(
        status="unavailable",
        events_received=0,
        events_processed=0,
        events_failed=0,
        avg_processing_time_ms=0,
    )
