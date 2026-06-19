"""
LangGraph agent tools.

Tools are domain service methods exposed as LangChain tools for use
within agent nodes.
"""

from src.agents.tools.analytics_tools import (
    get_daily_sales_tool,
    get_inventory_status_tool,
    get_branch_kpis_tool,
)
from src.agents.tools.cx_tools import (
    get_order_status_tool,
    get_customer_info_tool,
    create_ticket_tool,
    lookup_policy_tool,
    search_faq_tool,
)
from src.agents.tools.ops_tools import (
    summarize_report_tool,
    extract_kpis_tool,
    generate_tasks_tool,
    search_reports_tool,
)

__all__ = [
    # Analytics tools
    "get_branch_kpis_tool",
    "get_daily_sales_tool",
    "get_inventory_status_tool",
    # CX tools
    "get_order_status_tool",
    "get_customer_info_tool",
    "create_ticket_tool",
    "lookup_policy_tool",
    "search_faq_tool",
    # Ops tools
    "summarize_report_tool",
    "extract_kpis_tool",
    "generate_tasks_tool",
    "search_reports_tool",
]
