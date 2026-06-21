"""
Webhook payload parser — parse Odoo webhook payloads into structured data.
"""

from datetime import datetime, timezone
from typing import Any

import structlog

from src.infrastructure.webhooks.models import (
    WebhookEvent,
    WebhookEventType,
    InventoryUpdate,
    StockMovement,
    LowStockAlert,
)

logger = structlog.get_logger(__name__)


class WebhookPayloadParser:
    """
    Parse Odoo webhook payloads into structured models.

    Supports multiple Odoo models:
    - stock.quant (inventory levels)
    - stock.move (stock movements)
    - purchase.order (procurement)
    - sale.order (sales)
    - product.product (product updates)
    """

    # Odoo model to event type mapping
    MODEL_EVENT_MAP = {
        "stock.quant": WebhookEventType.INVENTORY_UPDATE,
        "stock.move": WebhookEventType.STOCK_MOVEMENT,
        "stock.move.line": WebhookEventType.STOCK_MOVEMENT,
        "purchase.order": WebhookEventType.PURCHASE_ORDER,
        "purchase.order.line": WebhookEventType.PURCHASE_ORDER,
        "sale.order": WebhookEventType.SALE_ORDER,
        "sale.order.line": WebhookEventType.SALE_ORDER,
        "product.product": WebhookEventType.PRODUCT_UPDATE,
        "product.template": WebhookEventType.PRODUCT_UPDATE,
    }

    def parse_event(self, payload: dict[str, Any]) -> WebhookEvent:
        """
        Parse raw webhook payload into WebhookEvent.

        Args:
            payload: Raw webhook payload from Odoo

        Returns:
            Parsed WebhookEvent
        """
        # Extract event type from model
        model = payload.get("model", payload.get("resource", "unknown"))
        event_type = self.MODEL_EVENT_MAP.get(model, WebhookEventType.UNKNOWN)

        # Extract action
        action = payload.get("action", payload.get("method", "update"))

        # Extract record info
        record_id = payload.get("id", payload.get("record_id", 0))
        if isinstance(record_id, str):
            try:
                record_id = int(record_id)
            except ValueError:
                record_id = 0

        event = WebhookEvent(
            event_id=payload.get("event_id", payload.get("uid", f"evt_{record_id}")),
            event_type=event_type,
            model=model,
            record_id=record_id,
            action=action,
            payload=payload.get("data", payload),
            metadata={
                "database": payload.get("database", ""),
                "user_id": payload.get("user_id", ""),
                "ip": payload.get("ip", ""),
            },
        )

        logger.info(
            "webhook.event_parsed",
            event_id=event.event_id,
            event_type=event.event_type.value,
            model=model,
            record_id=record_id,
        )

        return event

    def parse_inventory_update(self, payload: dict[str, Any]) -> InventoryUpdate:
        """
        Parse stock.quant payload into InventoryUpdate.

        Args:
            payload: stock.quant webhook payload

        Returns:
            Structured InventoryUpdate
        """
        # Handle nested Odoo data structure
        data = payload.get("data", payload)

        # Extract product info
        product = data.get("product_id", data.get("product", {}))
        if isinstance(product, (list, tuple)):
            product_id = str(product[0])
            product_name = product[1] if len(product) > 1 else "Unknown"
        elif isinstance(product, dict):
            product_id = str(product.get("id", ""))
            product_name = product.get("name", "Unknown")
        else:
            product_id = str(data.get("product_id", ""))
            product_name = data.get("product_name", "Unknown")

        # Extract location info
        location = data.get("location_id", data.get("location", {}))
        if isinstance(location, (list, tuple)):
            location_name = location[1] if len(location) > 1 else str(location[0])
        elif isinstance(location, dict):
            location_name = location.get("name", "")
        else:
            location_name = str(location)

        # Extract quantity
        quantity = float(data.get("quantity", data.get("qty", 0)))

        update = InventoryUpdate(
            product_id=product_id,
            product_name=product_name,
            sku=data.get("sku", data.get("default_code", None)),
            quantity=quantity,
            unit=data.get("uom_id", "Units") if isinstance(data.get("uom_id"), str) else "Units",
            location=location_name,
            warehouse=data.get("warehouse_name", None),
            branch_id=data.get("branch_id", None),
            branch_name=data.get("branch_name", None),
            min_stock=float(data.get("min_stock", data.get("reorder_min", 0))),
            max_stock=float(data.get("max_stock", data.get("reorder_max", 0))),
            reorder_point=float(data.get("reorder_point", data.get("reorder_min", 0))),
            cost_price=float(data.get("cost_price", data.get("standard_price", 0))),
            sale_price=float(data.get("sale_price", data.get("list_price", 0))),
            currency=data.get("currency", "SAR"),
            metadata={
                "location_id": data.get("location_id", ""),
                "package_id": data.get("package_id", ""),
                "owner_id": data.get("owner_id", ""),
            },
        )

        logger.info(
            "webhook.inventory_parsed",
            product_id=update.product_id,
            product_name=update.product_name,
            quantity=update.quantity,
            location=update.location,
            stock_health=update.stock_health,
        )

        return update

    def parse_stock_movement(self, payload: dict[str, Any]) -> StockMovement:
        """
        Parse stock.move payload into StockMovement.

        Args:
            payload: stock.move webhook payload

        Returns:
            Structured StockMovement
        """
        data = payload.get("data", payload)

        # Extract product info
        product = data.get("product_id", data.get("product", {}))
        if isinstance(product, (list, tuple)):
            product_id = str(product[0])
            product_name = product[1] if len(product) > 1 else "Unknown"
        elif isinstance(product, dict):
            product_id = str(product.get("id", ""))
            product_name = product.get("name", "Unknown")
        else:
            product_id = str(data.get("product_id", ""))
            product_name = data.get("product_name", "Unknown")

        # Extract locations
        from_loc = data.get("location_id", data.get("location_from", {}))
        to_loc = data.get("location_dest_id", data.get("location_to", {}))

        if isinstance(from_loc, (list, tuple)):
            from_location = from_loc[1] if len(from_loc) > 1 else str(from_loc[0])
        elif isinstance(from_loc, dict):
            from_location = from_loc.get("name", "")
        else:
            from_location = str(from_loc)

        if isinstance(to_loc, (list, tuple)):
            to_location = to_loc[1] if len(to_loc) > 1 else str(to_loc[0])
        elif isinstance(to_loc, dict):
            to_location = to_loc.get("name", "")
        else:
            to_location = str(to_loc)

        # Determine movement type
        quantity = float(data.get("product_uom_qty", data.get("quantity", 0)))
        if "customer" in to_location.lower() or "out" in to_location.lower():
            movement_type = "out"
        elif "supplier" in from_location.lower() or "in" in from_location.lower():
            movement_type = "in"
        else:
            movement_type = "transfer"

        return StockMovement(
            movement_id=str(data.get("id", data.get("move_id", ""))),
            product_id=product_id,
            product_name=product_name,
            from_location=from_location,
            to_location=to_location,
            quantity=quantity,
            movement_type=movement_type,
            reference=data.get("reference", data.get("name", "")),
            notes=data.get("note", ""),
        )

    def parse_low_stock_alert(self, payload: dict[str, Any]) -> LowStockAlert:
        """
        Parse low stock alert payload.

        Args:
            payload: Low stock alert payload

        Returns:
            Structured LowStockAlert
        """
        data = payload.get("data", payload)

        # Extract product info
        product = data.get("product_id", data.get("product", {}))
        if isinstance(product, (list, tuple)):
            product_id = str(product[0])
            product_name = product[1] if len(product) > 1 else "Unknown"
        elif isinstance(product, dict):
            product_id = str(product.get("id", ""))
            product_name = product.get("name", "Unknown")
        else:
            product_id = str(data.get("product_id", ""))
            product_name = data.get("product_name", "Unknown")

        current_qty = float(data.get("quantity", data.get("qty", 0)))
        reorder_point = float(data.get("reorder_point", data.get("reorder_min", 0)))

        # Determine severity
        if current_qty == 0:
            severity = "emergency"
            action = "URGENT: Out of stock - order immediately"
        elif current_qty <= reorder_point * 0.5:
            severity = "critical"
            action = "Critical: Place emergency order"
        else:
            severity = "warning"
            action = "Schedule replenishment order"

        return LowStockAlert(
            product_id=product_id,
            product_name=product_name,
            sku=data.get("sku", data.get("default_code", None)),
            current_quantity=current_qty,
            reorder_point=reorder_point,
            branch_id=data.get("branch_id", None),
            branch_name=data.get("branch_name", None),
            severity=severity,
            recommended_action=action,
        )
