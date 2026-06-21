"""
Odoo webhook infrastructure — real-time inventory sync.

Receives webhook events from Odoo ERP and syncs inventory data
to Qdrant vector store and Redis cache for real-time access.
"""

from src.infrastructure.webhooks.models import (
    WebhookEvent,
    WebhookEventType,
    InventoryUpdate,
)
from src.infrastructure.webhooks.parser import WebhookPayloadParser
from src.infrastructure.webhooks.sync import InventorySyncService
from src.infrastructure.webhooks.security import WebhookSecurity

__all__ = [
    "WebhookEvent",
    "WebhookEventType",
    "InventoryUpdate",
    "WebhookPayloadParser",
    "InventorySyncService",
    "WebhookSecurity",
]
