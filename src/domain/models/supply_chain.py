"""
Domain data models for supply chain management.

Used by the Supply Chain Agent for supplier management, procurement,
and auto-replenishment recommendations.
"""

from datetime import date, datetime
from pydantic import BaseModel, Field


class Supplier(BaseModel):
    """Supplier record from Odoo res.partner."""

    supplier_id: str
    name: str
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    country: str | None = None
    rating: float | None = Field(None, ge=0, le=5, description="Supplier rating 1-5")
    lead_time_days: int | None = Field(None, ge=0, description="Average delivery lead time")
    is_active: bool = True


class PurchaseOrder(BaseModel):
    """Purchase order from Odoo purchase.order."""

    order_id: str
    order_number: str
    supplier_id: str
    supplier_name: str
    order_date: date
    state: str = Field(description="draft, purchase, done, cancel")
    total_amount: float = Field(ge=0)
    currency: str = "SAR"
    expected_date: date | None = None
    items: list[dict] = Field(default_factory=list)


class ReplenishmentAlert(BaseModel):
    """Auto-replenishment alert for low stock."""

    product_id: str
    product_name: str
    branch_id: str
    branch_name: str
    current_stock: float = Field(ge=0)
    reorder_point: float = Field(ge=0)
    suggested_order_qty: float = Field(ge=0)
    preferred_supplier_id: str | None = None
    preferred_supplier_name: str | None = None
    estimated_cost: float = Field(ge=0)
    urgency: str = Field(description="critical, high, medium, low")
    days_until_stockout: float | None = None


class SupplierPerformance(BaseModel):
    """Supplier performance metrics."""

    supplier_id: str
    supplier_name: str
    period: str
    total_orders: int = Field(ge=0)
    on_time_delivery_pct: float = Field(ge=0, le=100)
    quality_score: float | None = Field(None, ge=0, le=5)
    avg_lead_time_days: float = Field(ge=0)
    total_spend: float = Field(ge=0)
    return_rate: float = Field(ge=0, le=1, description="Return rate as decimal")


class ProcurementRecommendation(BaseModel):
    """AI-generated procurement recommendation."""

    product_id: str
    product_name: str
    recommended_qty: float = Field(ge=0)
    supplier_id: str
    supplier_name: str
    estimated_cost: float = Field(ge=0)
    reason: str = Field(description="Arabic explanation")
    urgency: str = Field(description="critical, high, medium, low")
    expected_delivery: date | None = None
