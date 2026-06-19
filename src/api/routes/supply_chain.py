"""
Supply Chain API routes.

Provides endpoints for supplier management, procurement, and replenishment.
Designed for n8n consumption and direct API access.
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()


class ReplenishmentRequest(BaseModel):
    """Request for replenishment check."""

    threshold: float = Field(default=10.0, description="Stock threshold for alerts")


class PurchaseOrdersRequest(BaseModel):
    """Request for purchase orders."""

    supplier_id: str | None = Field(None, description="Supplier ID filter")
    days_back: int = Field(default=30, description="Days to look back")


class SupplierPerformanceRequest(BaseModel):
    """Request for supplier performance."""

    supplier_id: str = Field(..., description="Supplier ID to analyze")
    days_back: int = Field(default=90, description="Days to look back")


@router.post("/supply-chain/suppliers")
async def get_suppliers(request: Request) -> dict[str, Any]:
    """
    Get list of active suppliers.
    """
    supply_chain_service = request.app.state.supply_chain_service

    try:
        suppliers = await supply_chain_service.get_suppliers()

        return {
            "suppliers": [
                {
                    "supplier_id": s.supplier_id,
                    "name": s.name,
                    "email": s.email,
                    "phone": s.phone,
                    "city": s.city,
                    "is_active": s.is_active,
                }
                for s in suppliers
            ],
            "count": len(suppliers),
        }
    except Exception as e:
        logger.error("supply_chain.suppliers_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/supply-chain/replenishment")
async def check_replenishment(request: Request, body: ReplenishmentRequest) -> dict[str, Any]:
    """
    Check for products that need replenishment.
    """
    supply_chain_service = request.app.state.supply_chain_service

    try:
        alerts = await supply_chain_service.check_replenishment_needs(body.threshold)

        return {
            "threshold": body.threshold,
            "alerts": [
                {
                    "product_id": a.product_id,
                    "product_name": a.product_name,
                    "branch_id": a.branch_id,
                    "current_stock": a.current_stock,
                    "reorder_point": a.reorder_point,
                    "suggested_order_qty": a.suggested_order_qty,
                    "urgency": a.urgency,
                    "estimated_cost": a.estimated_cost,
                }
                for a in alerts
            ],
            "count": len(alerts),
        }
    except Exception as e:
        logger.error("supply_chain.replenishment_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/supply-chain/purchase-orders")
async def get_purchase_orders(request: Request, body: PurchaseOrdersRequest) -> dict[str, Any]:
    """
    Get recent purchase orders.
    """
    supply_chain_service = request.app.state.supply_chain_service

    try:
        end = date.today()
        start = date.fromordinal(end.toordinal() - body.days_back)

        orders = await supply_chain_service.get_purchase_orders(
            supplier_id=body.supplier_id,
            start_date=start,
            end_date=end,
        )

        return {
            "period": {"start": str(start), "end": str(end)},
            "orders": [
                {
                    "order_id": o.order_id,
                    "order_number": o.order_number,
                    "supplier_name": o.supplier_name,
                    "order_date": str(o.order_date),
                    "state": o.state,
                    "total_amount": o.total_amount,
                    "currency": o.currency,
                }
                for o in orders
            ],
            "count": len(orders),
        }
    except Exception as e:
        logger.error("supply_chain.purchase_orders_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/supply-chain/supplier-performance")
async def get_supplier_performance(request: Request, body: SupplierPerformanceRequest) -> dict[str, Any]:
    """
    Get supplier performance metrics.
    """
    supply_chain_service = request.app.state.supply_chain_service

    try:
        end = date.today()
        start = date.fromordinal(end.toordinal() - body.days_back)

        perf = await supply_chain_service.get_supplier_performance(
            body.supplier_id, start, end
        )

        if perf is None:
            return {"message": "No performance data found", "supplier_id": body.supplier_id}

        return {
            "supplier_id": perf.supplier_id,
            "period": perf.period,
            "total_orders": perf.total_orders,
            "on_time_delivery_pct": perf.on_time_delivery_pct,
            "avg_lead_time_days": perf.avg_lead_time_days,
            "total_spend": perf.total_spend,
        }
    except Exception as e:
        logger.error("supply_chain.performance_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
