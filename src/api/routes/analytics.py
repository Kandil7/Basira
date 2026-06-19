"""
Analytics API routes.

Provides endpoints for reports, KPIs, and inventory status.
Designed for n8n consumption and direct API access.
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()


class DailyReportRequest(BaseModel):
    """Request for daily branch report."""

    date: str = Field(..., description="Report date (YYYY-MM-DD)")
    branch_id: str | None = Field(None, description="Branch filter (optional)")
    include_comparison: bool = Field(default=True, description="Include period comparison")


class BranchKPIRequest(BaseModel):
    """Request for branch KPIs."""

    branch_ids: list[str] = Field(..., description="Branch IDs to analyze", min_length=1)
    period: str = Field(default="monthly", description="KPI period: daily, weekly, monthly")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")


class LowStockRequest(BaseModel):
    """Request for low stock check."""

    threshold: float = Field(default=10.0, description="Stock threshold for alerts")


@router.post("/reports/daily")
async def get_daily_report(request: Request, body: DailyReportRequest) -> dict[str, Any]:
    """
    Get daily branch report.

    Returns aggregated sales data for the specified date and branch.
    Designed for n8n daily report workflows.
    """
    analytics_service = request.app.state.analytics_service

    try:
        report_date = date.fromisoformat(body.date)
        report = await analytics_service.get_daily_sales(report_date, body.branch_id)

        return {
            "date": str(report.report_date),
            "branches": [
                {
                    "branch_id": report.branch_id,
                    "branch_name": report.branch_name,
                    "total_sales": report.total_sales,
                    "order_count": report.order_count,
                    "avg_order_value": report.avg_order_value,
                    "top_products": report.top_products,
                }
            ],
            "summary": {
                "total_sales": report.total_sales,
                "total_orders": report.order_count,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        logger.error("reports.daily_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kpis/branches")
async def get_branch_kpis(request: Request, body: BranchKPIRequest) -> dict[str, Any]:
    """
    Get KPIs for specified branches.

    Returns performance metrics for the given branches and date range.
    """
    analytics_service = request.app.state.analytics_service

    try:
        start_date = date.fromisoformat(body.start_date)
        end_date = date.fromisoformat(body.end_date)

        kpis = await analytics_service.get_branch_kpis(
            body.branch_ids, start_date, end_date
        )

        return {
            "kpis": [
                {
                    "branch_id": kpi.branch_id,
                    "branch_name": kpi.branch_name,
                    "metrics": {
                        "total_revenue": kpi.total_revenue,
                        "total_orders": kpi.total_orders,
                        "avg_order_value": kpi.avg_order_value,
                        "inventory_turnover": kpi.inventory_turnover,
                        "customer_satisfaction": kpi.customer_satisfaction,
                        "return_rate": kpi.return_rate,
                    },
                    "trends": {
                        "revenue_growth_pct": kpi.revenue_growth_pct,
                        "order_growth_pct": kpi.order_growth_pct,
                    },
                }
                for kpi in kpis
            ],
            "period": body.period,
            "date_range": {"start": body.start_date, "end": body.end_date},
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        logger.error("kpis.failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inventory/low-stock")
async def check_low_stock(request: Request, body: LowStockRequest) -> dict[str, Any]:
    """
    Check for low stock items.

    Returns products below the specified threshold.
    Designed for n8n low stock alert workflows.
    """
    analytics_service = request.app.state.analytics_service

    try:
        low_stock = await analytics_service.check_low_stock(body.threshold)

        return {
            "threshold": body.threshold,
            "low_stock_count": len(low_stock),
            "items": [
                {
                    "product_id": item.product_id,
                    "product_name": item.product_name,
                    "branch_id": item.branch_id,
                    "quantity_available": item.quantity_available,
                }
                for item in low_stock
            ],
        }
    except Exception as e:
        logger.error("inventory.low_stock_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
