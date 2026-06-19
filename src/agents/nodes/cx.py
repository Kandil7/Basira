"""
Customer Service (CX) Agent node.

Handles customer inquiries about orders, policies, and branches.
Uses RAG + Odoo data + Groq LLM for generating responses.

Prompt loaded from: prompts/cx_prompt.txt
"""

import re
from typing import Any

import structlog

from src.agents.llm import llm_chat
from src.agents.prompts import CX_PROMPT
from src.agents.state import AgentState
from src.config.settings import Settings
from src.domain.services.customer_service import CustomerService
from src.infrastructure.rag.retriever import Retriever

logger = structlog.get_logger(__name__)


async def cx_node(
    state: AgentState,
    settings: Settings,
    customer_service: CustomerService,
    retriever: Retriever,
) -> dict[str, Any]:
    """
    CX agent node — handles customer service queries.

    Combines RAG retrieval for policies with Odoo data for orders/customers.
    Gracefully handles individual tool failures without crashing the request.

    Tools used:
    - RAG retrieval (Qdrant) for policies/SOPs
    - Order status lookup (Odoo)
    - Customer info lookup (Odoo)

    Args:
        state: Current agent state
        settings: Application settings
        customer_service: Domain service for customer data
        retriever: RAG retriever for company docs

    Returns:
        State update with CX response.
    """
    query = state.get("user_query", "")
    context_parts: list[str] = []
    sources: list[str] = []
    tools_used: list[str] = []

    # ── Tool 1: RAG retrieval for policies/SOPs ─────────────────────
    try:
        rag_results = await retriever.retrieve(query, limit=3)
        if rag_results:
            rag_context = "\n\n".join(
                r.get("payload", {}).get("content", "") for r in rag_results
            )
            context_parts.append(f"Company Documentation:\n{rag_context}")
            tools_used.append("rag_retrieval")
            for r in rag_results:
                doc_id = r.get("payload", {}).get("document_id", "")
                if doc_id:
                    sources.append(f"doc:{doc_id}")
    except Exception as e:
        logger.warning("cx.rag_retrieval_error", error=str(e))

    # ── Tool 2: Order status lookup ──────────────────────────────────
    try:
        order_match = re.search(r"#(\d+)", query)
        if order_match:
            order_id = order_match.group(1)
            order = await customer_service.get_order_status(order_id)
            if order:
                context_parts.append(
                    f"Order #{order.order_number}:\n"
                    f"Status: {order.state}\n"
                    f"Amount: {order.total_amount:,.2f} {order.currency}\n"
                    f"Date: {order.order_date}"
                )
                tools_used.append("order_lookup")
                sources.append(f"order:{order.order_id}")
    except Exception as e:
        logger.warning("cx.order_lookup_error", error=str(e))

    # ── Tool 3: Customer info lookup ─────────────────────────────────
    try:
        phone_match = re.search(r"(\d{10,})", query)
        customer_match = re.search(r"عميل\s*(\d+)|customer\s*(\d+)", query, re.IGNORECASE)
        customer_id = None
        if customer_match:
            customer_id = customer_match.group(1) or customer_match.group(2)
        elif phone_match:
            # Could search by phone — stub for now
            pass

        if customer_id:
            customer = await customer_service.get_customer(customer_id)
            if customer:
                context_parts.append(
                    f"Customer: {customer.name}\n"
                    f"Phone: {customer.phone or customer.mobile or 'N/A'}\n"
                    f"City: {customer.city or 'N/A'}"
                )
                tools_used.append("customer_lookup")
                sources.append(f"customer:{customer.customer_id}")
    except Exception as e:
        logger.warning("cx.customer_lookup_error", error=str(e))

    # ── Generate response via Groq ───────────────────────────────────
    context = "\n\n".join(context_parts) if context_parts else "لا توجد بيانات محددة متاحة."
    user_msg = f"Context:\n{context}\n\nCustomer Query: {query}"

    try:
        response_text = await llm_chat(
            settings=settings,
            system_prompt=CX_PROMPT,
            user_message=user_msg,
            temperature=0.3,
        )
    except Exception as e:
        logger.error("cx.llm_error", error=str(e))
        response_text = "أعتذر، حدث خطأ أثناء معالجة طلبك. يرجى المحاولة مرة أخرى."

    logger.info(
        "cx.response_generated",
        query=query[:100],
        tools_used=tools_used,
        response_length=len(response_text),
    )

    return {
        "response": response_text,
        "agent": "cx",
        "context": {"rag_results": context_parts},
        "tools_used": tools_used,
        "sources": sources,
    }


def create_cx_node(
    settings: Settings,
    customer_service: CustomerService,
    retriever: Retriever,
):
    """Factory to create CX node with dependencies."""

    async def node(state: AgentState) -> dict[str, Any]:
        return await cx_node(state, settings, customer_service, retriever)

    return node
