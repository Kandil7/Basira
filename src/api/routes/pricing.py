"""
Pricing API routes.

Provides endpoints for pricing analysis, recommendations, and discount analysis.
Designed for n8n consumption and direct API access.
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()


class ProductPricesRequest(BaseModel):
    """Request for product pricing information."""

    product_ids: list[str] = Field(
        default_factory=list,
        description="Product IDs to check (empty for all)",
    )


class DiscountAnalysisRequest(BaseModel):
    """Request for discount analysis."""

    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")


@router.post("/pricing/products")
async def get_product_prices(request: Request, body: ProductPricesRequest) -> dict[str, Any]:
    """
    Get current pricing for products.

    Returns product prices, costs, and margins.
    """
    pricing_service = request.app.state.pricing_service

    try:
        prices = await pricing_service.get_product_prices(
            body.product_ids if body.product_ids else None
        )

        return {
            "products": [
                {
                    "product_id": p.product_id,
                    "product_name": p.product_name,
                    "current_price": p.current_price,
                    "cost_price": p.cost_price,
                    "margin_pct": p.margin_pct,
                    "currency": p.currency,
                }
                for p in prices
            ],
            "count": len(prices),
        }
    except Exception as e:
        logger.error("pricing.products_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pricing/recommendations")
async def get_pricing_recommendations(request: Request, body: ProductPricesRequest) -> dict[str, Any]:
    """
    Get AI-powered pricing recommendations.

    Analyzes margins and suggests optimal pricing.
    """
    pricing_service = request.app.state.pricing_service

    try:
        recs = await pricing_service.get_pricing_recommendations(
            body.product_ids if body.product_ids else None
        )

        return {
            "recommendations": [
                {
                    "product_id": r.product_id,
                    "product_name": r.product_name,
                    "current_price": r.current_price,
                    "recommended_price": r.recommended_price,
                    "confidence": r.confidence,
                    "reason": r.reason,
                    "expected_impact": r.expected_impact,
                    "risk_level": r.risk_level,
                }
                for r in recs
            ],
            "count": len(recs),
        }
    except Exception as e:
        logger.error("pricing.recommendations_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pricing/discounts")
async def analyze_discounts(request: Request, body: DiscountAnalysisRequest) -> dict[str, Any]:
    """
    Analyze discount and promotion performance.
    """
    pricing_service = request.app.state.pricing_service

    try:
        start = date.fromisoformat(body.start_date)
        end = date.fromisoformat(body.end_date)

        analyses = await pricing_service.analyze_discounts(start, end)

        return {
            "period": {"start": body.start_date, "end": body.end_date},
            "analyses": [
                {
                    "promotion_id": a.promotion_id,
                    "promotion_name": a.promotion_name,
                    "discount_pct": a.discount_pct,
                    "units_sold": a.units_sold_during,
                    "revenue": a.revenue_during,
                }
                for a in analyses
            ],
            "count": len(analyses),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        logger.error("pricing.discounts_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
