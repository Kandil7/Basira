"""
Inventory sync service — process webhook events and sync to vector store/cache.
"""

import time
from datetime import datetime, timezone
from typing import Any

import structlog

from src.infrastructure.webhooks.models import (
    WebhookEvent,
    WebhookEventType,
    InventoryUpdate,
    LowStockAlert,
)
from src.infrastructure.webhooks.parser import WebhookPayloadParser

logger = structlog.get_logger(__name__)


class InventorySyncService:
    """
    Process Odoo webhook events and sync inventory data.

    Features:
    - Real-time inventory updates to Qdrant
    - Cache invalidation for changed products
    - Low stock alert generation
    - Event history tracking
    - Metrics collection
    """

    def __init__(
        self,
        vector_store: Any = None,
        cache: Any = None,
        notification_callback: Any = None,
    ) -> None:
        """
        Initialize inventory sync service.

        Args:
            vector_store: Qdrant vector store for inventory search
            cache: Multi-tier cache for fast access
            notification_callback: Async function for sending notifications
        """
        self._vector_store = vector_store
        self._cache = cache
        self._notification_callback = notification_callback
        self._parser = WebhookPayloadParser()
        self._event_history: list[dict[str, Any]] = []
        self._stats = {
            "events_received": 0,
            "events_processed": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0,
        }

    async def process_event(self, event: WebhookEvent) -> dict[str, Any]:
        """
        Process a webhook event.

        Args:
            event: Parsed webhook event

        Returns:
            Processing result
        """
        start = time.time()
        self._stats["events_received"] += 1

        try:
            result: dict[str, Any] = {"success": False, "event_type": event.event_type.value}

            if event.event_type == WebhookEventType.INVENTORY_UPDATE:
                result = await self._process_inventory_update(event)

            elif event.event_type == WebhookEventType.STOCK_MOVEMENT:
                result = await self._process_stock_movement(event)

            elif event.event_type == WebhookEventType.LOW_STOCK_ALERT:
                result = await self._process_low_stock_alert(event)

            elif event.event_type == WebhookEventType.PRODUCT_UPDATE:
                result = await self._process_product_update(event)

            else:
                logger.info("webhook.unhandled_event", event_type=event.event_type.value)
                result = {"success": True, "message": "Event type not handled"}

            processing_time = (time.time() - start) * 1000
            self._stats["events_processed"] += 1
            self._stats["total_processing_time_ms"] += processing_time

            # Record event history
            self._event_history.append({
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "model": event.model,
                "record_id": event.record_id,
                "timestamp": event.timestamp.isoformat(),
                "processing_time_ms": round(processing_time, 2),
                "success": result.get("success", False),
            })

            # Keep only last 1000 events
            if len(self._event_history) > 1000:
                self._event_history = self._event_history[-1000:]

            return result

        except Exception as e:
            processing_time = (time.time() - start) * 1000
            self._stats["events_failed"] += 1
            self._stats["total_processing_time_ms"] += processing_time

            logger.error(
                "webhook.event_processing_failed",
                event_id=event.event_id,
                error=str(e),
                processing_time_ms=round(processing_time, 2),
            )

            return {"success": False, "error": str(e)}

    async def _process_inventory_update(self, event: WebhookEvent) -> dict[str, Any]:
        """Process inventory level update."""
        # Parse inventory data
        update = self._parser.parse_inventory_update(event.payload)

        # Update vector store with new inventory data
        if self._vector_store:
            try:
                # Create searchable inventory document
                doc_content = (
                    f"Product: {update.product_name} (SKU: {update.sku or 'N/A'})\n"
                    f"Quantity: {update.quantity} {update.unit}\n"
                    f"Location: {update.location or 'Unknown'}\n"
                    f"Branch: {update.branch_name or 'Unknown'}\n"
                    f"Status: {update.stock_health}\n"
                    f"Cost: {update.cost_price} {update.currency}\n"
                    f"Sale Price: {update.sale_price} {update.currency}"
                )

                # Upsert to vector store
                await self._vector_store.upsert(
                    collection_name="inventory",
                    points=[{
                        "id": f"inv_{update.product_id}",
                        "vector": [0.0] * 1536,  # Placeholder - will be replaced with real embedding
                        "payload": {
                            "content": doc_content,
                            "product_id": update.product_id,
                            "product_name": update.product_name,
                            "sku": update.sku,
                            "quantity": update.quantity,
                            "location": update.location,
                            "branch_id": update.branch_id,
                            "stock_health": update.stock_health,
                            "updated_at": update.timestamp.isoformat(),
                        },
                    }],
                )
                logger.info("webhook.inventory_vector_updated", product_id=update.product_id)
            except Exception as e:
                logger.warning("webhook.vector_update_failed", error=str(e))

        # Invalidate cache
        if self._cache:
            try:
                await self._cache.delete(f"inventory:{update.product_id}")
                await self._cache.delete(f"inventory:branch:{update.branch_id}")
                logger.info("webhook.inventory_cache_invalidated", product_id=update.product_id)
            except Exception as e:
                logger.warning("webhook.cache_invalidation_failed", error=str(e))

        # Check for low stock alerts
        if update.needs_reorder or update.is_low_stock:
            alert = LowStockAlert(
                product_id=update.product_id,
                product_name=update.product_name,
                sku=update.sku,
                current_quantity=update.quantity,
                reorder_point=update.reorder_point,
                branch_id=update.branch_id,
                branch_name=update.branch_name,
                severity="critical" if update.is_low_stock else "warning",
                recommended_action="Reorder needed" if update.needs_reorder else "Monitor",
            )
            await self._send_notification(alert)

        return {
            "success": True,
            "product_id": update.product_id,
            "quantity": update.quantity,
            "stock_health": update.stock_health,
        }

    async def _process_stock_movement(self, event: WebhookEvent) -> dict[str, Any]:
        """Process stock movement event."""
        movement = self._parser.parse_stock_movement(event.payload)

        logger.info(
            "webhook.stock_movement",
            product_id=movement.product_id,
            from_location=movement.from_location,
            to_location=movement.to_location,
            quantity=movement.quantity,
            movement_type=movement.movement_type,
        )

        # Invalidate affected location caches
        if self._cache:
            try:
                await self._cache.delete(f"inventory:location:{movement.from_location}")
                await self._cache.delete(f"inventory:location:{movement.to_location}")
            except Exception as e:
                logger.warning("webhook.cache_invalidation_failed", error=str(e))

        return {
            "success": True,
            "movement_id": movement.movement_id,
            "product_id": movement.product_id,
            "movement_type": movement.movement_type,
        }

    async def _process_low_stock_alert(self, event: WebhookEvent) -> dict[str, Any]:
        """Process low stock alert."""
        alert = self._parser.parse_low_stock_alert(event.payload)
        await self._send_notification(alert)

        return {
            "success": True,
            "product_id": alert.product_id,
            "severity": alert.severity,
        }

    async def _process_product_update(self, event: WebhookEvent) -> dict[str, Any]:
        """Process product update event."""
        data = event.payload.get("data", event.payload)
        product_id = str(data.get("id", data.get("product_id", "")))

        # Invalidate product cache
        if self._cache:
            try:
                await self._cache.delete(f"product:{product_id}")
                logger.info("webhook.product_cache_invalidated", product_id=product_id)
            except Exception as e:
                logger.warning("webhook.cache_invalidation_failed", error=str(e))

        return {"success": True, "product_id": product_id}

    async def _send_notification(self, alert: LowStockAlert) -> None:
        """Send low stock notification."""
        if self._notification_callback:
            try:
                await self._notification_callback(alert)
            except Exception as e:
                logger.warning("webhook.notification_failed", error=str(e))

        # Log alert regardless
        logger.warning(
            "webhook.low_stock_alert",
            product_id=alert.product_id,
            product_name=alert.product_name,
            quantity=alert.current_quantity,
            reorder_point=alert.reorder_point,
            severity=alert.severity,
            branch=alert.branch_name,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get sync service statistics."""
        avg_time = (
            self._stats["total_processing_time_ms"] / self._stats["events_processed"]
            if self._stats["events_processed"] > 0 else 0
        )
        return {
            **self._stats,
            "avg_processing_time_ms": round(avg_time, 2),
            "history_size": len(self._event_history),
        }

    def get_recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent webhook events."""
        return self._event_history[-limit:]
