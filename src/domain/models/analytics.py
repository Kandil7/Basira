"""
Domain data models for the analytics module.

All models are Pydantic BaseModel instances with full type annotations.
These represent the core business entities for sales, inventory, and KPIs.
"""

from datetime import date, datetime, timezone

from pydantic import BaseModel, Field


class SalesData(BaseModel):
    """Individual sales record from Odoo."""

    order_id: str = Field(..., description="Odoo sale.order ID")
    order_date: date = Field(..., description="Date of the order")
    branch_id: str = Field(..., description="Branch/warehouse ID")
    branch_name: str = Field(..., description="Branch display name")
    customer_id: str | None = Field(None, description="Customer ID if known")
    product_id: str = Field(..., description="Product ID")
    product_name: str = Field(..., description="Product display name")
    quantity: float = Field(..., gt=0, description="Quantity sold")
    unit_price: float = Field(..., ge=0, description="Unit price in local currency")
    total_amount: float = Field(..., ge=0, description="Line total (qty × price)")
    currency: str = Field(default="SAR", description="Currency code")


class DailyReport(BaseModel):
    """Aggregated daily report for a branch."""

    report_date: date = Field(..., description="Report date")
    branch_id: str = Field(..., description="Branch ID")
    branch_name: str = Field(..., description="Branch name")
    total_sales: float = Field(..., ge=0, description="Total sales amount")
    order_count: int = Field(..., ge=0, description="Number of orders")
    avg_order_value: float = Field(..., ge=0, description="Average order value")
    top_products: list[dict] = Field(default_factory=list, description="Top selling products")
    sales_data: list[SalesData] = Field(default_factory=list, description="Detailed sales records")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Report generation time")


class BranchComparison(BaseModel):
    """Comparison between two periods for a branch."""

    branch_id: str
    branch_name: str
    current_period: DailyReport
    previous_period: DailyReport | None = None
    sales_change_pct: float = Field(description="Percentage change in sales")
    order_change_pct: float = Field(description="Percentage change in order count")


class InventoryItem(BaseModel):
    """Current inventory status for a product."""

    product_id: str
    product_name: str
    branch_id: str
    branch_name: str
    quantity_on_hand: float = Field(ge=0, description="Current stock level")
    quantity_reserved: float = Field(ge=0, description="Reserved quantity")
    quantity_available: float = Field(ge=0, description="Available = on_hand - reserved")
    reorder_point: float | None = Field(None, description="Minimum stock before reorder")
    needs_reorder: bool = Field(default=False, description="True if below reorder point")


class BranchKPI(BaseModel):
    """Key Performance Indicators for a branch."""

    branch_id: str
    branch_name: str
    period: str = Field(description="KPI period (daily, weekly, monthly)")
    start_date: date
    end_date: date
    total_revenue: float = Field(ge=0)
    total_orders: int = Field(ge=0)
    avg_order_value: float = Field(ge=0)
    inventory_turnover: float | None = Field(None, description="Inventory turnover ratio")
    customer_satisfaction: float | None = Field(None, ge=0, le=5, description="CSAT score 1-5")
    return_rate: float | None = Field(None, ge=0, le=1, description="Return rate as decimal")
    revenue_growth_pct: float | None = Field(None, description="Revenue growth vs previous period")
    order_growth_pct: float | None = Field(None, description="Order growth vs previous period")


class AnalyticsQuery(BaseModel):
    """User query for analytics from Arabic NLU."""

    raw_query: str = Field(..., description="Original user query text")
    intent: str = Field(description="Parsed intent: sales, inventory, comparison, recommendation")
    branch_filter: str | None = Field(None, description="Branch to filter by")
    date_range: dict | None = Field(None, description="Date range with start/end")
    metrics: list[str] = Field(default_factory=list, description="Requested metrics")
