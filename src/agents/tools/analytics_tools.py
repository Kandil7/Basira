"""
Analytics tools — LangChain tool definitions for analytics operations.

These wrap domain services as callable tools for LangGraph agents.
"""

from datetime import date
from typing import Any

from langchain_core.tools import tool
import structlog

logger = structlog.get_logger(__name__)

# NOTE: These tools use a module-level service reference.
# In production, use dependency injection or a tool registry pattern.
_analytics_service: Any = None


def set_analytics_service(service: Any) -> None:
    """Set the analytics service for tool use."""
    global _analytics_service
    _analytics_service = service


@tool
async def get_daily_sales_tool(branch_id: str = "", date_str: str = "") -> str:
    """
    Get daily sales report for a branch.

    Args:
        branch_id: Branch ID to filter by (empty for all branches)
        date_str: Date in YYYY-MM-DD format (empty for today)

    Returns:
        Formatted daily sales report.
    """
    if _analytics_service is None:
        return "Analytics service not initialized"

    target_date = date.fromisoformat(date_str) if date_str else date.today()
    branch = branch_id if branch_id else None

    try:
        report = await _analytics_service.get_daily_sales(target_date, branch)
        return (
            f"Daily Sales Report ({report.report_date}):\n"
            f"Branch: {report.branch_name}\n"
            f"Total Sales: {report.total_sales:,.2f} SAR\n"
            f"Orders: {report.order_count}\n"
            f"Avg Order Value: {report.avg_order_value:,.2f} SAR"
        )
    except Exception as e:
        logger.error("tool.get_daily_sales_failed", error=str(e))
        return f"Error fetching sales data: {str(e)}"


@tool
async def get_inventory_status_tool(branch_id: str = "") -> str:
    """
    Get current inventory status.

    Args:
        branch_id: Branch ID to filter by (empty for all branches)

    Returns:
        Formatted inventory status.
    """
    if _analytics_service is None:
        return "Analytics service not initialized"

    branch = branch_id if branch_id else None

    try:
        items = await _analytics_service.get_inventory_status(branch)
        low_stock = [i for i in items if i.quantity_available < 10]
        return (
            f"Inventory Status:\n"
            f"Total Products: {len(items)}\n"
            f"Low Stock Items: {len(low_stock)}\n"
            f"Products Below Threshold: {', '.join(i.product_name for i in low_stock[:5])}"
        )
    except Exception as e:
        logger.error("tool.get_inventory_failed", error=str(e))
        return f"Error fetching inventory: {str(e)}"


@tool
async def get_branch_kpis_tool(
    branch_ids: str = "",
    start_date: str = "",
    end_date: str = "",
) -> str:
    """
    Get KPIs for specified branches over a date range.

    Args:
        branch_ids: Comma-separated branch IDs
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Formatted KPI report.
    """
    if _analytics_service is None:
        return "Analytics service not initialized"

    branches = [b.strip() for b in branch_ids.split(",") if b.strip()]
    if not branches:
        return "Please provide at least one branch ID."

    start = date.fromisoformat(start_date) if start_date else date.today()
    end = date.fromisoformat(end_date) if end_date else date.today()

    try:
        kpis = await _analytics_service.get_branch_kpis(branches, start, end)
        lines = ["Branch KPIs Report:"]
        for kpi in kpis:
            lines.append(
                f"\n{kpi.branch_name}:\n"
                f"  Revenue: {kpi.total_revenue:,.2f} SAR\n"
                f"  Orders: {kpi.total_orders}\n"
                f"  Avg Order: {kpi.avg_order_value:,.2f} SAR"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error("tool.get_kpis_failed", error=str(e))
        return f"Error fetching KPIs: {str(e)}"
