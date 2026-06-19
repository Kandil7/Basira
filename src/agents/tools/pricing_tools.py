"""
Pricing tools — LangChain tool definitions for pricing and promotions operations.

These wrap the PricingService as callable tools for the Pricing Agent.
"""

from typing import Any

from langchain_core.tools import tool
import structlog

logger = structlog.get_logger(__name__)

_pricing_service: Any = None


def set_pricing_service(service: Any) -> None:
    """Set the pricing service for tool use."""
    global _pricing_service
    _pricing_service = service


@tool
async def get_product_prices_tool(product_ids: str = "") -> str:
    """
    Get current pricing information for products.

    Args:
        product_ids: Comma-separated product IDs (empty for all products)

    Returns:
        Formatted pricing report with current prices and margins.
    """
    if _pricing_service is None:
        return "Pricing service not initialized"

    ids = [pid.strip() for pid in product_ids.split(",") if pid.strip()] or None

    try:
        prices = await _pricing_service.get_product_prices(ids)
        if not prices:
            return "No product pricing data found."

        lines = ["Product Pricing Report:"]
        for p in prices:
            lines.append(
                f"\n{p.product_name} (ID: {p.product_id}):\n"
                f"  Current Price: {p.current_price:,.2f} {p.currency}\n"
                f"  Cost Price: {p.cost_price:,.2f} {p.currency}\n"
                f"  Margin: {p.margin_pct:.1f}%"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error("tool.get_product_prices_failed", error=str(e))
        return f"Error fetching product prices: {str(e)}"


@tool
async def get_pricing_recommendations_tool(product_ids: str = "") -> str:
    """
    Get AI-powered pricing recommendations for products.

    Analyzes margins and suggests optimal pricing.

    Args:
        product_ids: Comma-separated product IDs (empty for analysis of all)

    Returns:
        Pricing recommendations with reasons and expected impact.
    """
    if _pricing_service is None:
        return "Pricing service not initialized"

    ids = [pid.strip() for pid in product_ids.split(",") if pid.strip()] or None

    try:
        recs = await _pricing_service.get_pricing_recommendations(ids)
        if not recs:
            return "No pricing recommendations at this time."

        lines = ["Pricing Recommendations:"]
        for r in recs:
            lines.append(
                f"\n{r.product_name}:\n"
                f"  Current: {r.current_price:,.2f} → Recommended: {r.recommended_price:,.2f}\n"
                f"  Confidence: {r.confidence:.0%}\n"
                f"  Risk: {r.risk_level}\n"
                f"  Reason: {r.reason}\n"
                f"  Expected Impact: {r.expected_impact}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error("tool.get_pricing_recommendations_failed", error=str(e))
        return f"Error generating pricing recommendations: {str(e)}"


@tool
async def analyze_discounts_tool(start_date: str = "", end_date: str = "") -> str:
    """
    Analyze discount and promotion performance.

    Compares sales during promotion vs baseline period.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Discount analysis with lift metrics.
    """
    if _pricing_service is None:
        return "Pricing service not initialized"

    from datetime import date as date_type

    try:
        start = date_type.fromisoformat(start_date) if start_date else date_type.today()
        end = date_type.fromisoformat(end_date) if end_date else date_type.today()

        analyses = await _pricing_service.analyze_discounts(start, end)
        if not analyses:
            return "No discount data found for the specified period."

        lines = [f"Discount Analysis ({start} to {end}):"]
        for a in analyses:
            lines.append(
                f"\n{a.promotion_name}:\n"
                f"  Product: {a.product_name}\n"
                f"  Discount: {a.discount_pct:.0f}% ({a.original_price:,.2f} → {a.discounted_price:,.2f})\n"
                f"  Units Sold: {a.units_sold_during}\n"
                f"  Revenue: {a.revenue_during:,.2f} SAR"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error("tool.analyze_discounts_failed", error=str(e))
        return f"Error analyzing discounts: {str(e)}"
