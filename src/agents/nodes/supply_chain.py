"""
Supply Chain Agent node.

Handles supplier management, procurement, and auto-replenishment.
Uses SupplyChainService + Groq LLM for generating Arabic responses.

Prompt loaded from: prompts/supply_chain_prompt.txt
"""

from typing import Any

import structlog

from src.agents.llm import llm_chat
from src.agents.prompts import SUPPLY_CHAIN_PROMPT
from src.agents.state import AgentState
from src.config.settings import Settings
from src.domain.services.supply_chain_service import SupplyChainService

logger = structlog.get_logger(__name__)


async def supply_chain_node(
    state: AgentState,
    settings: Settings,
    supply_chain_service: SupplyChainService,
) -> dict[str, Any]:
    """
    Supply chain agent node — handles procurement and supplier queries.

    Uses SupplyChainService for data retrieval and Groq LLM for response generation.

    Args:
        state: Current agent state
        settings: Application settings
        supply_chain_service: Domain service for supply chain data

    Returns:
        State update with supply chain response.
    """
    query = state.get("user_query", "")
    context_parts: list[str] = []
    tools_used: list[str] = []

    try:
        # Detect supply chain intent keywords
        is_suppliers = any(w in query for w in ["موردين", "supplier", "مورد", "vendor"])
        is_replenish = any(w in query for w in ["重新", "replenish", "إعادة", "stock补充", "مخزون"])
        is_orders = any(w in query for w in ["طلبات شراء", "purchase order", "order"])
        is_performance = any(w in query for w in ["أداء", "performance", "تقييم", "rating"])

        if is_suppliers:
            suppliers = await supply_chain_service.get_suppliers()
            if suppliers:
                supplier_lines = [f"- {s.name} ({s.city or 'N/A'})" for s in suppliers[:10]]
                context_parts.append("Active Suppliers:\n" + "\n".join(supplier_lines))
                tools_used.append("supplier_list")

        if is_replenish:
            alerts = await supply_chain_service.check_replenishment_needs()
            if alerts:
                alert_lines = [
                    f"- {a.product_name} ({a.branch_name}): {a.current_stock:.0f} units, "
                    f"urgency: {a.urgency}"
                    for a in alerts[:10]
                ]
                context_parts.append("Replenishment Alerts:\n" + "\n".join(alert_lines))
                tools_used.append("replenishment_check")

        if is_orders:
            from datetime import date, timedelta
            end = date.today()
            start = end - timedelta(days=30)
            orders = await supply_chain_service.get_purchase_orders(start_date=start, end_date=end)
            if orders:
                order_lines = [
                    f"- {o.order_number}: {o.total_amount:,.2f} SAR ({o.state})"
                    for o in orders[:10]
                ]
                context_parts.append("Recent Purchase Orders:\n" + "\n".join(order_lines))
                tools_used.append("purchase_orders")

    except Exception as e:
        logger.warning("supply_chain.data_fetch_error", error=str(e))
        context_parts.append("ملاحظة: لا يمكن جلب بيانات سلسلة التوريد في الوقت الحالي.")

    context = "\n\n".join(context_parts) if context_parts else "لا توجد بيانات سلسلة توريد محددة متاحة."

    user_msg = f"Context:\n{context}\n\nUser Query: {query}"

    try:
        response_text = await llm_chat(
            settings=settings,
            system_prompt=SUPPLY_CHAIN_PROMPT,
            user_message=user_msg,
            temperature=0.3,
        )
    except Exception as e:
        logger.error("supply_chain.llm_error", error=str(e))
        response_text = "أعتذر، حدث خطأ أثناء معالجة طلب سلسلة التوريد. يرجى المحاولة مرة أخرى."

    logger.info(
        "supply_chain.response_generated",
        query=query[:100],
        tools_used=tools_used,
        response_length=len(response_text),
    )

    return {
        "response": response_text,
        "agent": "supply_chain",
        "context": {"data": context_parts},
        "tools_used": tools_used,
    }


def create_supply_chain_node(
    settings: Settings,
    supply_chain_service: SupplyChainService,
):
    """Factory to create supply chain node with dependencies."""

    async def node(state: AgentState) -> dict[str, Any]:
        return await supply_chain_node(state, settings, supply_chain_service)

    return node
