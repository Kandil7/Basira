"""
Supply chain tools — LangChain tool definitions for procurement and supplier operations.

These wrap the SupplyChainService as callable tools for the Supply Chain Agent.
"""

from typing import Any

from langchain_core.tools import tool
import structlog

logger = structlog.get_logger(__name__)

_supply_chain_service: Any = None


def set_supply_chain_service(service: Any) -> None:
    """Set the supply chain service for tool use."""
    global _supply_chain_service
    _supply_chain_service = service


@tool
async def get_suppliers_tool() -> str:
    """
    Get list of active suppliers.

    Returns:
        Formatted list of suppliers with contact information.
    """
    if _supply_chain_service is None:
        return "Supply chain service not initialized"

    try:
        suppliers = await _supply_chain_service.get_suppliers()
        if not suppliers:
            return "No suppliers found."

        lines = ["Active Suppliers:"]
        for s in suppliers[:20]:
            lines.append(
                f"\n- {s.name} (ID: {s.supplier_id})\n"
                f"  Email: {s.email or 'N/A'}\n"
                f"  Phone: {s.phone or 'N/A'}\n"
                f"  City: {s.city or 'N/A'}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error("tool.get_suppliers_failed", error=str(e))
        return f"Error fetching suppliers: {str(e)}"


@tool
async def check_replenishment_tool(threshold: str = "10") -> str:
    """
    Check for products that need replenishment.

    Args:
        threshold: Minimum stock level to trigger alert (default: 10)

    Returns:
        List of products needing reorder with urgency levels.
    """
    if _supply_chain_service is None:
        return "Supply chain service not initialized"

    try:
        threshold_val = float(threshold)
        alerts = await _supply_chain_service.check_replenishment_needs(threshold_val)
        if not alerts:
            return "All products are adequately stocked."

        lines = [f"Replenishment Alerts ({len(alerts)} products):"]
        for a in alerts[:15]:
            lines.append(
                f"\n- {a.product_name} (Branch: {a.branch_name}):\n"
                f"  Current Stock: {a.current_stock:.0f}\n"
                f"  Reorder Point: {a.reorder_point:.0f}\n"
                f"  Suggested Order: {a.suggested_order_qty:.0f}\n"
                f"  Urgency: {a.urgency}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error("tool.check_replenishment_failed", error=str(e))
        return f"Error checking replenishment: {str(e)}"


@tool
async def get_purchase_orders_tool(
    supplier_id: str = "",
    days_back: str = "30",
) -> str:
    """
    Get recent purchase orders.

    Args:
        supplier_id: Optional supplier ID to filter
        days_back: Number of days to look back (default: 30)

    Returns:
        Formatted list of recent purchase orders.
    """
    if _supply_chain_service is None:
        return "Supply chain service not initialized"

    from datetime import date, timedelta

    try:
        end = date.today()
        start = end - timedelta(days=int(days_back))
        sid = supplier_id if supplier_id else None

        orders = await _supply_chain_service.get_purchase_orders(sid, start, end)
        if not orders:
            return "No purchase orders found for the specified period."

        lines = [f"Purchase Orders ({start} to {end}):"]
        for o in orders[:15]:
            lines.append(
                f"\n- {o.order_number}:\n"
                f"  Supplier: {o.supplier_name}\n"
                f"  Date: {o.order_date}\n"
                f"  Status: {o.state}\n"
                f"  Amount: {o.total_amount:,.2f} {o.currency}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error("tool.get_purchase_orders_failed", error=str(e))
        return f"Error fetching purchase orders: {str(e)}"


@tool
async def get_supplier_performance_tool(supplier_id: str) -> str:
    """
    Get supplier performance metrics.

    Args:
        supplier_id: Supplier ID to analyze

    Returns:
        Supplier performance report with delivery and quality metrics.
    """
    if _supply_chain_service is None:
        return "Supply chain service not initialized"

    try:
        perf = await _supply_chain_service.get_supplier_performance(supplier_id)
        if perf is None:
            return f"No performance data found for supplier {supplier_id}."

        return (
            f"Supplier Performance Report:\n"
            f"Supplier: {perf.supplier_name}\n"
            f"Period: {perf.period}\n"
            f"Total Orders: {perf.total_orders}\n"
            f"On-Time Delivery: {perf.on_time_delivery_pct:.1f}%\n"
            f"Avg Lead Time: {perf.avg_lead_time_days:.1f} days\n"
            f"Total Spend: {perf.total_spend:,.2f} SAR"
        )
    except Exception as e:
        logger.error("tool.get_supplier_performance_failed", error=str(e))
        return f"Error fetching supplier performance: {str(e)}"
