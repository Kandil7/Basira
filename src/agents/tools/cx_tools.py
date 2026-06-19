"""
CX tools — LangChain tool definitions for customer service operations.

These wrap domain services as callable tools for the CX agent.

Tools:
- get_order_status_tool: Look up order status by ID
- get_customer_info_tool: Look up customer by ID or phone
- create_ticket_tool: Create a support ticket
- search_faq_tool: Search company FAQ/policies via RAG
"""

from typing import Any

from langchain_core.tools import tool
import structlog

logger = structlog.get_logger(__name__)

_customer_service: Any = None
_retriever: Any = None


def set_cx_services(customer_service: Any, retriever: Any) -> None:
    """Set services for CX tool use."""
    global _customer_service, _retriever
    _customer_service = customer_service
    _retriever = retriever


@tool
async def get_order_status_tool(order_id: str) -> str:
    """
    Look up order status by order ID.

    Args:
        order_id: The order ID to look up (e.g., "12345")

    Returns:
        Order status information including state, amount, and date.
    """
    if _customer_service is None:
        return "Customer service not initialized"

    try:
        order = await _customer_service.get_order_status(order_id)
        if order is None:
            return f"Order #{order_id} not found."

        return (
            f"Order #{order.order_number}:\n"
            f"Status: {order.state}\n"
            f"Amount: {order.total_amount:,.2f} {order.currency}\n"
            f"Date: {order.order_date}\n"
            f"Branch: {order.branch_name or 'N/A'}"
        )
    except Exception as e:
        logger.error("tool.get_order_status_failed", error=str(e))
        return f"Error looking up order: {str(e)}"


@tool
async def get_customer_info_tool(customer_id: str = "", phone: str = "") -> str:
    """
    Look up customer information by ID or phone number.

    Args:
        customer_id: Customer/partner ID (e.g., "123")
        phone: Customer phone number (alternative to ID)

    Returns:
        Customer information including name, contact, and city.
    """
    if _customer_service is None:
        return "Customer service not initialized"

    try:
        # Try by ID first
        if customer_id:
            customer = await _customer_service.get_customer(customer_id)
            if customer:
                return (
                    f"Customer #{customer.customer_id}:\n"
                    f"Name: {customer.name}\n"
                    f"Email: {customer.email or 'N/A'}\n"
                    f"Phone: {customer.phone or customer.mobile or 'N/A'}\n"
                    f"City: {customer.city or 'N/A'}\n"
                    f"Is Company: {customer.is_company}"
                )
            return f"Customer #{customer_id} not found."

        # Phone lookup stub — TODO: implement when Odoo phone search is available
        if phone:
            return f"Phone lookup for {phone} — not yet implemented. Please provide customer ID."

        return "Please provide either customer_id or phone number."
    except Exception as e:
        logger.error("tool.get_customer_info_failed", error=str(e))
        return f"Error looking up customer: {str(e)}"


@tool
async def create_ticket_tool(
    customer_id: str,
    subject: str,
    description: str,
    priority: str = "normal",
) -> str:
    """
    Create a support ticket for a customer.

    Args:
        customer_id: Customer/partner ID
        subject: Ticket subject line
        description: Detailed description of the issue
        priority: Priority level (low, normal, high, urgent)

    Returns:
        Confirmation of ticket creation.
    """
    if _customer_service is None:
        return "Customer service not initialized"

    try:
        ticket = await _customer_service.create_support_ticket(
            customer_id=customer_id,
            subject=subject,
            description=description,
            priority=priority,
        )
        return (
            f"Support ticket created:\n"
            f"Ticket #: {ticket.ticket_number}\n"
            f"Subject: {ticket.subject}\n"
            f"Priority: {ticket.priority}\n"
            f"Status: {ticket.state}"
        )
    except Exception as e:
        logger.error("tool.create_ticket_failed", error=str(e))
        return f"Error creating ticket: {str(e)}"


@tool
async def lookup_policy_tool(question: str) -> str:
    """
    Search company policies, SOPs, and FAQs.

    Uses RAG (Qdrant) to find relevant policy documents.

    Args:
        question: Policy question to search for (e.g., "ما هي سياسة الإرجاع؟")

    Returns:
        Relevant policy content from company documentation.
    """
    if _retriever is None:
        return "Retriever not initialized"

    try:
        context = await _retriever.retrieve_with_context(question, limit=3)
        return context
    except Exception as e:
        logger.error("tool.lookup_policy_failed", error=str(e))
        return f"Error searching policies: {str(e)}"


# ── Legacy alias for backward compatibility ─────────────────────────
search_faq_tool = lookup_policy_tool
