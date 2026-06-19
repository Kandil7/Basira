"""
Advanced analytics — trend analysis, period comparison, and forecasting.

Extends the base AnalyticsService with advanced analytical capabilities
for deeper business insights.
"""

from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel, Field

import structlog

from src.domain.interfaces.odoo_client import OdooClientInterface

logger = structlog.get_logger(__name__)


class TrendAnalysis(BaseModel):
    """Trend analysis result for a metric."""

    metric_name: str
    current_value: float
    previous_value: float
    change_pct: float = Field(description="Percentage change")
    trend: str = Field(description="up, down, stable")
    period: str = Field(description="Analysis period")


class PeriodComparison(BaseModel):
    """Comparison between two time periods."""

    metric_name: str
    current_period: dict[str, Any]
    previous_period: dict[str, Any]
    change_pct: float
    summary: str = Field(description="Arabic summary of the comparison")


class SalesForecast(BaseModel):
    """Simple sales forecast based on historical data."""

    product_id: str | None = None
    branch_id: str | None = None
    forecast_date: date
    predicted_sales: float
    confidence: float = Field(ge=0, le=1)
    basis: str = Field(description="Basis for prediction")


class AdvancedAnalyticsService:
    """
    Advanced analytics service extending base analytics.

    Provides trend analysis, period comparisons, and simple forecasting.
    """

    def __init__(self, odoo_client: OdooClientInterface) -> None:
        self._odoo = odoo_client

    async def analyze_trends(
        self,
        branch_id: str | None = None,
        days_back: int = 30,
    ) -> list[TrendAnalysis]:
        """
        Analyze sales trends by comparing recent vs previous period.

        Args:
            branch_id: Optional branch filter
            days_back: Number of days to analyze

        Returns:
            List of TrendAnalysis for each metric.
        """
        today = date.today()
        current_start = today - timedelta(days=days_back)
        previous_start = current_start - timedelta(days=days_back)
        previous_end = current_start

        trends: list[TrendAnalysis] = []

        # Analyze sales trend
        current_sales = await self._get_total_sales(current_start, today, branch_id)
        previous_sales = await self._get_total_sales(previous_start, previous_end, branch_id)

        sales_change = self._calc_change(current_sales, previous_sales)
        trends.append(
            TrendAnalysis(
                metric_name="إجمالي المبيعات",
                current_value=current_sales,
                previous_value=previous_sales,
                change_pct=sales_change,
                trend="up" if sales_change > 0 else "down" if sales_change < 0 else "stable",
                period=f"آخر {days_back} يوم",
            )
        )

        # Analyze order count trend
        current_orders = await self._get_order_count(current_start, today, branch_id)
        previous_orders = await self._get_order_count(previous_start, previous_end, branch_id)

        order_change = self._calc_change(current_orders, previous_orders)
        trends.append(
            TrendAnalysis(
                metric_name="عدد الطلبات",
                current_value=current_orders,
                previous_value=previous_orders,
                change_pct=order_change,
                trend="up" if order_change > 0 else "down" if order_change < 0 else "stable",
                period=f"آخر {days_back} يوم",
            )
        )

        # Analyze average order value trend
        avg_current = current_sales / current_orders if current_orders > 0 else 0
        avg_previous = previous_sales / previous_orders if previous_orders > 0 else 0

        avg_change = self._calc_change(avg_current, avg_previous)
        trends.append(
            TrendAnalysis(
                metric_name="متوسط قيمة الطلب",
                current_value=avg_current,
                previous_value=avg_previous,
                change_pct=avg_change,
                trend="up" if avg_change > 0 else "down" if avg_change < 0 else "stable",
                period=f"آخر {days_back} يوم",
            )
        )

        return trends

    async def compare_periods(
        self,
        current_start: date,
        current_end: date,
        previous_start: date,
        previous_end: date,
        branch_id: str | None = None,
    ) -> list[PeriodComparison]:
        """
        Compare two time periods in detail.

        Args:
            current_start: Current period start
            current_end: Current period end
            previous_start: Previous period start
            previous_end: Previous period end
            branch_id: Optional branch filter

        Returns:
            List of PeriodComparison for each metric.
        """
        comparisons: list[PeriodComparison] = []

        # Sales comparison
        current_sales = await self._get_total_sales(current_start, current_end, branch_id)
        previous_sales = await self._get_total_sales(previous_start, previous_end, branch_id)

        sales_change = self._calc_change(current_sales, previous_sales)
        comparisons.append(
            PeriodComparison(
                metric_name="إجمالي المبيعات",
                current_period={
                    "value": current_sales,
                    "start": str(current_start),
                    "end": str(current_end),
                },
                previous_period={
                    "value": previous_sales,
                    "start": str(previous_start),
                    "end": str(previous_end),
                },
                change_pct=sales_change,
                summary=self._generate_comparison_summary(
                    "المبيعات", current_sales, previous_sales, sales_change, "SAR"
                ),
            )
        )

        # Order count comparison
        current_orders = await self._get_order_count(current_start, current_end, branch_id)
        previous_orders = await self._get_order_count(previous_start, previous_end, branch_id)

        order_change = self._calc_change(current_orders, previous_orders)
        comparisons.append(
            PeriodComparison(
                metric_name="عدد الطلبات",
                current_period={"value": current_orders},
                previous_period={"value": previous_orders},
                change_pct=order_change,
                summary=self._generate_comparison_summary(
                    "الطلبات", current_orders, previous_orders, order_change, ""
                ),
            )
        )

        return comparisons

    async def forecast_sales(
        self,
        branch_id: str | None = None,
        days_ahead: int = 7,
    ) -> list[SalesForecast]:
        """
        Simple sales forecast based on recent average.

        Uses the average daily sales from the last 30 days to predict
        the next N days.

        Args:
            branch_id: Optional branch filter
            days_ahead: Number of days to forecast

        Returns:
            List of SalesForecast for each day.
        """
        today = date.today()
        lookback_start = today - timedelta(days=30)

        total_sales = await self._get_total_sales(lookback_start, today, branch_id)
        avg_daily_sales = total_sales / 30 if total_sales > 0 else 0

        forecasts: list[SalesForecast] = []
        for i in range(1, days_ahead + 1):
            forecast_date = today + timedelta(days=i)
            forecasts.append(
                SalesForecast(
                    branch_id=branch_id,
                    forecast_date=forecast_date,
                    predicted_sales=round(avg_daily_sales, 2),
                    confidence=0.5,  # Low confidence for simple average
                    basis="متوسط المبيعات اليومية من آخر 30 يوم",
                )
            )

        return forecasts

    # ── Private helpers ──────────────────────────────────────────────

    async def _get_total_sales(
        self,
        start_date: date,
        end_date: date,
        branch_id: str | None,
    ) -> float:
        """Get total sales for a date range."""
        domain: list[list] = [
            ["date_order", ">=", str(start_date)],
            ["date_order", "<=", str(end_date)],
        ]
        if branch_id:
            domain.append(["warehouse_id", "=", int(branch_id)])

        records = await self._odoo.search_read(
            model="sale.order",
            domain=domain,
            fields=["amount_total"],
            limit=5000,
        )
        return sum(r.get("amount_total", 0) for r in records)

    async def _get_order_count(
        self,
        start_date: date,
        end_date: date,
        branch_id: str | None,
    ) -> int:
        """Get order count for a date range."""
        domain: list[list] = [
            ["date_order", ">=", str(start_date)],
            ["date_order", "<=", str(end_date)],
        ]
        if branch_id:
            domain.append(["warehouse_id", "=", int(branch_id)])

        records = await self._odoo.search_read(
            model="sale.order",
            domain=domain,
            fields=["id"],
            limit=5000,
        )
        return len(records)

    @staticmethod
    def _calc_change(current: float, previous: float) -> float:
        """Calculate percentage change."""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 2)

    @staticmethod
    def _generate_comparison_summary(
        metric_name: str,
        current: float,
        previous: float,
        change_pct: float,
        unit: str,
    ) -> str:
        """Generate Arabic summary of period comparison."""
        if change_pct > 0:
            return f"ارتفعت {metric_name} بنسبة {change_pct:.1f}% مقارنة بالفترة السابقة"
        elif change_pct < 0:
            return f"انخفضت {metric_name} بنسبة {abs(change_pct):.1f}% مقارنة بالفترة السابقة"
        else:
            return f"ظابت {metric_name} مقارنة بالفترة السابقة"
