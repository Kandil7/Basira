"""
Pricing Agent node.

Handles pricing analysis, discount optimization, and promotion performance.
Uses PricingService + Groq LLM for generating Arabic responses.

Prompt loaded from: prompts/pricing_prompt.txt
"""

from typing import Any

import structlog

from src.agents.llm import llm_chat
from src.agents.prompts import PRICING_PROMPT
from src.agents.state import AgentState
from src.config.settings import Settings
from src.domain.services.pricing_service import PricingService

logger = structlog.get_logger(__name__)


async def pricing_node(
    state: AgentState,
    settings: Settings,
    pricing_service: PricingService,
) -> dict[str, Any]:
    """
    Pricing agent node — handles pricing and promotions queries.

    Uses PricingService for data retrieval and Groq LLM for response generation.

    Args:
        state: Current agent state
        settings: Application settings
        pricing_service: Domain service for pricing data

    Returns:
        State update with pricing response.
    """
    query = state.get("user_query", "")
    context_parts: list[str] = []
    tools_used: list[str] = []

    try:
        # Detect pricing intent keywords
        is_prices = any(w in query for w in ["سعر", "price", "أسعار", "cost"])
        is_discount = any(w in query for w in ["خصم", "discount", "عرض", "promotion"])
        is_recommend = any(w in query for w in ["توصية", "recommend", "اقتراح", "تحسين"])

        if is_prices:
            prices = await pricing_service.get_product_prices()
            if prices:
                price_lines = []
                for p in prices[:10]:
                    price_lines.append(
                        f"- {p.product_name}: {p.current_price:,.2f} SAR (margin: {p.margin_pct:.1f}%)"
                    )
                context_parts.append(
                    f"Product Prices:\n" + "\n".join(price_lines)
                )
                tools_used.append("product_prices")

        if is_discount:
            from datetime import date, timedelta
            end = date.today()
            start = end - timedelta(days=30)
            analyses = await pricing_service.analyze_discounts(start, end)
            if analyses:
                discount_lines = []
                for a in analyses[:5]:
                    discount_lines.append(
                        f"- {a.promotion_name}: {a.discount_pct:.0f}% off, "
                        f"Units: {a.units_sold_during}, Revenue: {a.revenue_during:,.2f} SAR"
                    )
                context_parts.append(
                    f"Recent Discounts:\n" + "\n".join(discount_lines)
                )
                tools_used.append("discount_analysis")

        if is_recommend:
            recs = await pricing_service.get_pricing_recommendations()
            if recs:
                rec_lines = []
                for r in recs[:5]:
                    rec_lines.append(
                        f"- {r.product_name}: {r.current_price:,.2f} → {r.recommended_price:,.2f} "
                        f"({r.reason})"
                    )
                context_parts.append(
                    f"Pricing Recommendations:\n" + "\n".join(rec_lines)
                )
                tools_used.append("pricing_recommendations")

    except Exception as e:
        logger.warning("pricing.data_fetch_error", error=str(e))
        context_parts.append("ملاحظة: لا يمكن جلب بيانات الأسعار في الوقت الحالي.")

    context = "\n\n".join(context_parts) if context_parts else "لا توجد بيانات أسعار محددة متاحة."

    user_msg = f"Context:\n{context}\n\nUser Query: {query}"

    try:
        response_text = await llm_chat(
            settings=settings,
            system_prompt=PRICING_PROMPT,
            user_message=user_msg,
            temperature=0.3,
        )
    except Exception as e:
        logger.error("pricing.llm_error", error=str(e))
        response_text = "أعتذر، حدث خطأ أثناء تحليل طلب الأسعار. يرجى المحاولة مرة أخرى."

    logger.info(
        "pricing.response_generated",
        query=query[:100],
        tools_used=tools_used,
        response_length=len(response_text),
    )

    return {
        "response": response_text,
        "agent": "pricing",
        "context": {"data": context_parts},
        "tools_used": tools_used,
    }


def create_pricing_node(
    settings: Settings,
    pricing_service: PricingService,
):
    """Factory to create pricing node with dependencies."""

    async def node(state: AgentState) -> dict[str, Any]:
        return await pricing_node(state, settings, pricing_service)

    return node
