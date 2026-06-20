"""
Export API routes.

Provides endpoints for exporting reports in PDF, Excel, CSV, and JSON formats.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import structlog

from src.infrastructure.export.engine import ExportEngine, ExportFormat

logger = structlog.get_logger(__name__)

router = APIRouter()

# Shared export engine
_export_engine = ExportEngine()


class ExportRequest(BaseModel):
    """Request for report export."""
    data: dict[str, Any] = Field(..., description="Data to export")
    format: str = Field(default="pdf", description="Export format: pdf, excel, csv, json")
    title: str = Field(default="Report", description="Report title")


class DailyReportExportRequest(BaseModel):
    """Request for daily report export."""
    date: str = Field(..., description="Report date (YYYY-MM-DD)")
    branch_id: str | None = Field(None, description="Branch filter (optional)")
    format: str = Field(default="pdf", description="Export format")


@router.post("/export/report")
async def export_report(request: Request, body: ExportRequest) -> StreamingResponse:
    """
    Export arbitrary data as a report.

    Supports PDF, Excel, CSV, and JSON formats.
    """
    try:
        format_map = {
            "pdf": ExportFormat.PDF,
            "excel": ExportFormat.EXCEL,
            "xlsx": ExportFormat.EXCEL,
            "csv": ExportFormat.CSV,
            "json": ExportFormat.JSON,
        }

        export_format = format_map.get(body.format.lower())
        if not export_format:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format: {body.format}. Use: pdf, excel, csv, json"
            )

        buffer = _export_engine.export(
            data=body.data,
            format=export_format,
            title=body.title,
        )

        content_type = _export_engine.get_export_content_type(export_format)
        extension = _export_engine.get_export_extension(export_format)
        filename = f"report{extension}"

        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        logger.error("export.failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/daily")
async def export_daily_report(
    request: Request,
    body: DailyReportExportRequest,
) -> StreamingResponse:
    """
    Export daily sales report in the specified format.

    Fetches data from analytics service and exports it.
    """
    from datetime import date as date_cls

    try:
        analytics_service = request.app.state.analytics_service
        report_date = date_cls.fromisoformat(body.date)
        report = await analytics_service.get_daily_sales(report_date, body.branch_id)

        # Format data for export
        data = {
            "التاريخ": str(report.report_date),
            "الفرع": report.branch_name,
            "إجمالي المبيعات": f"{report.total_sales:,.2f} ريال",
            "عدد الطلبات": report.order_count,
            "متوسط قيمة الطلب": f"{report.avg_order_value:,.2f} ريال",
        }

        if report.top_products:
            data["المنتجات الأكثر مبيعاً"] = {
                p.get("name", ""): f"{p.get('quantity', 0)} وحدة"
                for p in report.top_products[:5]
            }

        format_map = {
            "pdf": ExportFormat.PDF,
            "excel": ExportFormat.EXCEL,
            "xlsx": ExportFormat.EXCEL,
            "csv": ExportFormat.CSV,
            "json": ExportFormat.JSON,
        }

        export_format = format_map.get(body.format.lower(), ExportFormat.PDF)
        buffer = _export_engine.export(
            data=data,
            format=export_format,
            title=f"تقرير المبيعات اليومي - {body.date}",
        )

        content_type = _export_engine.get_export_content_type(export_format)
        extension = _export_engine.get_export_extension(export_format)
        filename = f"daily_report_{body.date}{extension}"

        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        logger.error("export.daily_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/kpis")
async def export_kpis_report(
    request: Request,
    branch_ids: list[str],
    start_date: str,
    end_date: str,
    format: str = "pdf",
) -> StreamingResponse:
    """
    Export branch KPIs report.
    """
    from datetime import date as date_cls

    try:
        analytics_service = request.app.state.analytics_service
        start = date_cls.fromisoformat(start_date)
        end = date_cls.fromisoformat(end_date)

        kpis = await analytics_service.get_branch_kpis(branch_ids, start, end)

        data = {
            "الفترة": f"من {start_date} إلى {end_date}",
            "الفروع": {},
        }

        for kpi in kpis:
            data["الفروع"][kpi.branch_name] = {
                "الإيرادات": f"{kpi.total_revenue:,.2f} ريال",
                "عدد الطلبات": kpi.total_orders,
                "متوسط الطلب": f"{kpi.avg_order_value:,.2f} ريال",
                "نمو الإيرادات": f"{kpi.revenue_growth_pct:.1f}%",
            }

        format_map = {
            "pdf": ExportFormat.PDF,
            "excel": ExportFormat.EXCEL,
            "xlsx": ExportFormat.EXCEL,
            "csv": ExportFormat.CSV,
            "json": ExportFormat.JSON,
        }

        export_format = format_map.get(format.lower(), ExportFormat.PDF)
        buffer = _export_engine.export(
            data=data,
            format=export_format,
            title="تقرير مؤشرات الأداء",
        )

        content_type = _export_engine.get_export_content_type(export_format)
        extension = _export_engine.get_export_extension(export_format)
        filename = f"kpis_report{extension}"

        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        logger.error("export.kpis_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
