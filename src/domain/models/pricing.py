"""
Domain data models for pricing and promotions analytics.

Used by the Pricing Agent for price optimization, discount analysis,
and promotion performance tracking.
"""

from datetime import date, datetime
from pydantic import BaseModel, Field


class ProductPrice(BaseModel):
    """Current price information for a product."""

    product_id: str
    product_name: str
    current_price: float = Field(ge=0, description="Current selling price")
    cost_price: float = Field(ge=0, description="Cost/purchase price")
    margin_pct: float = Field(description="Profit margin percentage")
    currency: str = "SAR"
    last_updated: datetime | None = None


class DiscountAnalysis(BaseModel):
    """Analysis of a discount or promotion."""

    promotion_id: str
    promotion_name: str
    product_id: str
    product_name: str
    original_price: float = Field(ge=0)
    discounted_price: float = Field(ge=0)
    discount_pct: float = Field(ge=0, le=100, description="Discount percentage")
    start_date: date
    end_date: date
    units_sold_during: int = Field(ge=0, description="Units sold during promotion")
    revenue_during: float = Field(ge=0, description="Revenue during promotion")
    units_sold_baseline: int = Field(ge=0, description="Units sold in same period without promotion")
    revenue_baseline: float = Field(ge=0, description="Baseline revenue without promotion")
    lift_pct: float | None = Field(None, description="Sales lift percentage")


class PricingRecommendation(BaseModel):
    """AI-generated pricing recommendation."""

    product_id: str
    product_name: str
    current_price: float
    recommended_price: float
    confidence: float = Field(ge=0, le=1, description="Confidence in recommendation")
    reason: str = Field(description="Arabic explanation of recommendation")
    expected_impact: str = Field(description="Expected impact on sales/revenue")
    risk_level: str = Field(description="low, medium, high")
    data_sources: list[str] = Field(default_factory=list)


class CompetitorPrice(BaseModel):
    """Competitor pricing data."""

    product_id: str
    product_name: str
    our_price: float
    competitor_name: str
    competitor_price: float
    price_difference_pct: float = Field(description="Our price vs competitor (%)")
    last_checked: datetime | None = None


class PricingQuery(BaseModel):
    """Parsed pricing query from user."""

    raw_query: str
    intent: str = Field(description="price_check, discount_analysis, recommendation, competitor")
    product_filter: str | None = None
    date_range: dict | None = None
