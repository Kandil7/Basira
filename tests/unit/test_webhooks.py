"""
Webhook tests — models, parser, security, sync service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.webhooks.models import (
    WebhookEvent,
    WebhookEventType,
    InventoryUpdate,
    StockMovement,
    LowStockAlert,
)
from src.infrastructure.webhooks.parser import WebhookPayloadParser
from src.infrastructure.webhooks.security import WebhookSecurity
from src.infrastructure.webhooks.sync import InventorySyncService


class TestWebhookEvent:
    """Test WebhookEvent model."""

    def test_create_event(self):
        event = WebhookEvent(
            event_id="evt_123",
            event_type=WebhookEventType.INVENTORY_UPDATE,
            model="stock.quant",
            record_id=123,
            action="write",
        )
        assert event.event_id == "evt_123"
        assert event.event_type == WebhookEventType.INVENTORY_UPDATE

    def test_event_types(self):
        assert WebhookEventType.INVENTORY_UPDATE.value == "inventory_update"
        assert WebhookEventType.STOCK_MOVEMENT.value == "stock_movement"
        assert WebhookEventType.LOW_STOCK_ALERT.value == "low_stock_alert"


class TestInventoryUpdate:
    """Test InventoryUpdate model."""

    def test_stock_health_healthy(self):
        update = InventoryUpdate(
            product_id="1",
            product_name="Test",
            quantity=100,
            min_stock=10,
            reorder_point=20,
        )
        assert update.stock_health == "healthy"

    def test_stock_health_low(self):
        update = InventoryUpdate(
            product_id="1",
            product_name="Test",
            quantity=15,
            reorder_point=20,
        )
        assert update.needs_reorder is True
        assert update.stock_health == "low"

    def test_stock_health_critical(self):
        update = InventoryUpdate(
            product_id="1",
            product_name="Test",
            quantity=5,
            min_stock=10,
        )
        assert update.is_low_stock is True
        assert update.stock_health == "critical"

    def test_stock_health_overstocked(self):
        update = InventoryUpdate(
            product_id="1",
            product_name="Test",
            quantity=500,
            max_stock=100,
        )
        assert update.is_overstocked is True
        assert update.stock_health == "overstocked"


class TestWebhookPayloadParser:
    """Test WebhookPayloadParser."""

    def setup_method(self):
        self.parser = WebhookPayloadParser()

    def test_parse_event_inventory(self):
        payload = {
            "model": "stock.quant",
            "id": 123,
            "action": "write",
            "data": {"quantity": 50},
        }
        event = self.parser.parse_event(payload)
        assert event.event_type == WebhookEventType.INVENTORY_UPDATE
        assert event.record_id == 123

    def test_parse_event_unknown(self):
        payload = {"model": "unknown.model", "id": 1}
        event = self.parser.parse_event(payload)
        assert event.event_type == WebhookEventType.UNKNOWN

    def test_parse_inventory_update(self):
        payload = {
            "data": {
                "product_id": [1, "Hليب طازج"],
                "quantity": 100,
                "location_id": [1, "Main Warehouse"],
                "sku": "MLK-001",
            }
        }
        update = self.parser.parse_inventory_update(payload)
        assert update.product_id == "1"
        assert update.product_name == "Hليب طازج"
        assert update.quantity == 100
        assert update.sku == "MLK-001"

    def test_parse_stock_movement(self):
        payload = {
            "data": {
                "id": "MOV-001",
                "product_id": [1, "Product A"],
                "location_id": [1, "Warehouse"],
                "location_dest_id": [2, "Store"],
                "product_uom_qty": 50,
            }
        }
        movement = self.parser.parse_stock_movement(payload)
        assert movement.product_id == "1"
        assert movement.quantity == 50
        assert movement.movement_type == "transfer"

    def test_parse_low_stock_alert(self):
        payload = {
            "data": {
                "product_id": [1, "Critical Product"],
                "quantity": 0,
                "reorder_point": 10,
            }
        }
        alert = self.parser.parse_low_stock_alert(payload)
        assert alert.severity == "emergency"
        assert alert.current_quantity == 0


class TestWebhookSecurity:
    """Test WebhookSecurity."""

    def setup_method(self):
        self.security = WebhookSecurity(secret="test-secret-key")

    def test_compute_signature(self):
        payload = b'{"test": "data"}'
        sig = self.security._compute_signature(payload)
        assert len(sig) == 64  # SHA-256 hex digest

    def test_validate_signature(self):
        payload = b'{"test": "data"}'
        sig = self.security._compute_signature(payload)
        assert self.security.validate_signature(payload, sig) is True

    def test_invalid_signature(self):
        payload = b'{"test": "data"}'
        assert self.security.validate_signature(payload, "invalid_sig") is False

    def test_ip_whitelist_no_config(self):
        assert self.security.check_ip_whitelist("127.0.0.1") is True

    def test_ip_whitelist_allowed(self):
        security = WebhookSecurity(secret="key", allowed_ips=["127.0.0.1"])
        assert security.check_ip_whitelist("127.0.0.1") is True

    def test_ip_whitelist_blocked(self):
        security = WebhookSecurity(secret="key", allowed_ips=["10.0.0.1"])
        assert security.check_ip_whitelist("127.0.0.1") is False

    def test_replay_protection(self):
        assert self.security.check_replay("nonce-123") is True
        assert self.security.check_replay("nonce-123") is False  # Replay detected

    def test_get_stats(self):
        stats = self.security.get_stats()
        assert "validated" in stats
        assert "rejected" in stats


class TestInventorySyncService:
    """Test InventorySyncService."""

    def setup_method(self):
        self.mock_vector_store = AsyncMock()
        self.mock_cache = AsyncMock()
        self.service = InventorySyncService(
            vector_store=self.mock_vector_store,
            cache=self.mock_cache,
        )

    @pytest.mark.asyncio
    async def test_process_inventory_update(self):
        event = WebhookEvent(
            event_id="evt_1",
            event_type=WebhookEventType.INVENTORY_UPDATE,
            model="stock.quant",
            record_id=1,
            action="write",
            payload={
                "data": {
                    "product_id": [1, "Test Product"],
                    "quantity": 50,
                    "location_id": [1, "Warehouse"],
                }
            },
        )
        result = await self.service.process_event(event)
        assert result["success"] is True
        assert result["quantity"] == 50

    @pytest.mark.asyncio
    async def test_process_low_stock_alert(self):
        event = WebhookEvent(
            event_id="evt_2",
            event_type=WebhookEventType.LOW_STOCK_ALERT,
            model="stock.quant",
            record_id=2,
            action="write",
            payload={
                "data": {
                    "product_id": [1, "Low Product"],
                    "quantity": 5,
                    "reorder_point": 20,
                }
            },
        )
        result = await self.service.process_event(event)
        assert result["success"] is True
        assert result["severity"] == "critical"

    def test_get_stats(self):
        stats = self.service.get_stats()
        assert "events_received" in stats
        assert "events_processed" in stats

    def test_get_recent_events(self):
        events = self.service.get_recent_events()
        assert isinstance(events, list)


class TestLowStockAlert:
    """Test LowStockAlert model."""

    def test_emergency_severity(self):
        alert = LowStockAlert(
            product_id="1",
            product_name="Test",
            current_quantity=0,
            reorder_point=10,
            severity="emergency",
        )
        assert alert.severity == "emergency"
