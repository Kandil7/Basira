"""
Analytical Agent node.

Handles sales, inventory, and branch performance queries.
Uses domain services + Groq LLM for generating Arabic responses.

Prompt loaded from: prompts/analytical_prompt.txt
"""

from typing import Any

import structlog

from src.agents.llm import llm_chat
from src.agents.prompts import ANALYTICAL_PROMPT
from src.agents.state import AgentState
from src.config.settings import Settings
from src.domain.services.analytics_service import AnalyticsService

logger = structlog.get_logger(__name__)

async def analytical_node(
    state: AgentState,
    settings: Settings,
    analytics_service: AnalyticsService,
) -> dict[str, Any]:
    """
    Analytical agent node — processes sales/inventory/KPI queries.

    Uses AnalyticsService for data retrieval and Groq LLM for response generation.
    Gracefully handles tool failures and returns partial results.

    Args:
        state: Current agent state
        settings: Application settings
        analytics_service: Domain service for analytics data

    Returns:
        State update with analytical response.
    """
    query = state.get("user_query", "")
    context_parts: list[str] = []
    tools_used: list[str] = []

    # Fetch relevant data based on query keywords
    try:
        if any(word in query for word in ["مبيعات", "sales", "بيع"]):
            from datetime import date

            today = date.today()
            report = await analytics_service.get_daily_sales(today)
            context_parts.append(
                f"Daily Sales Report ({today}):\n"
                f"Total Sales: {report.total_sales:,.2f} SAR\n"
                f"Orders: {report.order_count}\n"
                f"Avg Order: {report.avg_order_value:,.2f} SAR"
            )
            tools_used.append("analytics_service")

        if any(word in query for word in ["مخزون", "inventory", "stock"]):
            inventory = await analytics_service.get_inventory_status()
            low_stock = [i for i in inventory if i.quantity_available < 10]
            context_parts.append(
                f"Inventory Status: {len(inventory)} products tracked\n"
                f"Low Stock Items: {len(low_stock)}"
            )
            tools_used.append("inventory_service")
    except Exception as e:
        logger.warning("analytical.data_fetch_error", error=str(e))
        context_parts.append("ملاحظة: لا يمكن جلب البيانات في الوقت الحالي. يرجى المحاولة لاحقاً.")

    context = "\n\n".join(context_parts) if context_parts else "لا توجد بيانات محددة متاحة."

    # Generate response via Groq
    user_msg = f"Context:\n{context}\n\nUser Query: {query}"
    try:
        response_text = await llm_chat(
            settings=settings,
            system_prompt=ANALYTICAL_PROMPT,
            user_message=user_msg,
            temperature=0.3,
        )
    except Exception as e:
        logger.error("analytical.llm_error", error=str(e))
        response_text = "أعتذر، حدث خطأ أثناء تحليل طلبك. يرجى المحاولة مرة أخرى."

    logger.info(
        "analytical.response_generated",
        query=query[:100],
        tools_used=tools_used,
        response_length=len(response_text),
    )

    return {
        "response": response_text,
        "agent": "analytical",
        "context": {"data": context_parts},
        "tools_used": tools_used,
    }


def create_analytical_node(
    settings: Settings,
    analytics_service: AnalyticsService,
):
    """Factory to create analytical node with dependencies."""

    async def node(state: AgentState) -> dict[str, Any]:
        return await analytical_node(state, settings, analytics_service)

    return node
