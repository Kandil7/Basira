"""
Webhook models — data structures for Odoo webhook events.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WebhookEventType(Enum):
    """Odoo webhook event types."""
    INVENTORY_UPDATE = "inventory_update"
    STOCK_MOVEMENT = "stock_movement"
    PURCHASE_ORDER = "purchase_order"
    SALE_ORDER = "sale_order"
    PRODUCT_UPDATE = "product_update"
    LOW_STOCK_ALERT = "low_stock_alert"
    UNKNOWN = "unknown"


class WebhookEvent(BaseModel):
    """Raw webhook event from Odoo."""
    event_id: str = Field(description="Unique event identifier")
    event_type: WebhookEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model: str = Field(description="Odoo model that triggered the event")
    record_id: int = Field(description="Odoo record ID")
    action: str = Field(description="Action: create, update, delete")
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class InventoryUpdate(BaseModel):
    """Processed inventory update for sync."""
    product_id: str
    product_name: str
    sku: str | None = None
    quantity: float
    unit: str = "Units"
    location: str | None = None
    warehouse: str | None = None
    branch_id: str | None = None
    branch_name: str | None = None
    min_stock: float = 0
    max_stock: float = 0
    reorder_point: float = 0
    cost_price: float = 0
    sale_price: float = 0
    currency: str = "SAR"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def needs_reorder(self) -> bool:
        """Check if stock is below reorder point."""
        return self.quantity <= self.reorder_point

    @property
    def is_low_stock(self) -> bool:
        """Check if stock is critically low."""
        return self.quantity <= self.min_stock

    @property
    def is_overstocked(self) -> bool:
        """Check if stock exceeds maximum."""
        return self.max_stock > 0 and self.quantity > self.max_stock

    @property
    def stock_health(self) -> str:
        """Get stock health status."""
        if self.is_low_stock:
            return "critical"
        elif self.needs_reorder:
            return "low"
        elif self.is_overstocked:
            return "overstocked"
        else:
            return "healthy"


class StockMovement(BaseModel):
    """Stock movement event."""
    movement_id: str
    product_id: str
    product_name: str
    from_location: str
    to_location: str
    quantity: float
    movement_type: str  # "in", "out", "transfer"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reference: str | None = None
    notes: str | None = None


class LowStockAlert(BaseModel):
    """Low stock alert for notifications."""
    product_id: str
    product_name: str
    sku: str | None = None
    current_quantity: float
    reorder_point: float
    branch_id: str | None = None
    branch_name: str | None = None
    severity: str = "warning"  # "warning", "critical", "emergency"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    recommended_action: str = ""
