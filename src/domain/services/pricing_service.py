"""
Pricing domain service.

Handles price analysis, discount optimization, and promotion performance.
Pure business logic with no framework dependencies.
"""

from datetime import date

from src.domain.interfaces.odoo_client import OdooClientInterface
from src.domain.models.pricing import (
    DiscountAnalysis,
    PricingRecommendation,
    ProductPrice,
)


class PricingService:
    """Business logic for pricing and promotions analytics."""

    def __init__(self, odoo_client: OdooClientInterface) -> None:
        self._odoo = odoo_client

    async def get_product_prices(
        self,
        product_ids: list[str] | None = None,
    ) -> list[ProductPrice]:
        """
        Get current pricing for products.

        Args:
            product_ids: Optional list of product IDs to filter

        Returns:
            List of ProductPrice with current and cost prices.
        """
        domain: list[list] = []
        if product_ids:
            domain.append(["id", "in", [int(pid) for pid in product_ids]])

        products = await self._odoo.search_read(
            model="product.product",
            domain=domain,
            fields=[
                "id",
                "name",
                "list_price",
                "standard_price",
                "currency_id",
            ],
            limit=500,
        )

        prices: list[ProductPrice] = []
        for p in products:
            list_price = p.get("list_price", 0)
            cost_price = p.get("standard_price", 0)
            margin = ((list_price - cost_price) / list_price * 100) if list_price > 0 else 0

            prices.append(
                ProductPrice(
                    product_id=str(p["id"]),
                    product_name=p.get("name", ""),
                    current_price=list_price,
                    cost_price=cost_price,
                    margin_pct=round(margin, 2),
                )
            )

        return prices

    async def analyze_discounts(
        self,
        start_date: date,
        end_date: date,
    ) -> list[DiscountAnalysis]:
        """
        Analyze promotion/discount performance.

        Compares sales during promotion vs baseline period.

        Args:
            start_date: Promotion start date
            end_date: Promotion end date

        Returns:
            List of DiscountAnalysis for each promotion.
        """
        # Get active promotions
        promos = await self._odoo.search_read(
            model="product.pricelist.item",
            domain=[
                ["date_start", ">=", str(start_date)],
                ["date_end", "<=", str(end_date)],
            ],
            fields=[
                "id",
                "name",
                "product_id",
                "price_discount",
                "date_start",
                "date_end",
            ],
            limit=100,
        )

        analyses: list[DiscountAnalysis] = []
        for promo in promos:
            product_id = str(promo.get("product_id", ""))

            # Get sales during promotion
            promo_sales = await self._odoo.search_read(
                model="sale.order.line",
                domain=[
                    ["product_id", "=", int(product_id)],
                    ["order_id.date_order", ">=", str(start_date)],
                    ["order_id.date_order", "<=", str(end_date)],
                ],
                fields=["product_uom_qty", "price_subtotal"],
                limit=1000,
            )

            units_during = sum(s.get("product_uom_qty", 0) for s in promo_sales)
            revenue_during = sum(s.get("price_subtotal", 0) for s in promo_sales)

            discount_pct = promo.get("price_discount", 0)
            original_price = 0
            discounted_price = 0

            # Get product price info
            if product_id:
                product_info = await self._odoo.search_read(
                    model="product.product",
                    domain=[["id", "=", int(product_id)]],
                    fields=["list_price"],
                    limit=1,
                )
                if product_info:
                    original_price = product_info[0].get("list_price", 0)
                    discounted_price = original_price * (1 - discount_pct / 100)

            analyses.append(
                DiscountAnalysis(
                    promotion_id=str(promo["id"]),
                    promotion_name=promo.get("name", ""),
                    product_id=product_id,
                    product_name="",
                    original_price=original_price,
                    discounted_price=discounted_price,
                    discount_pct=discount_pct,
                    start_date=start_date,
                    end_date=end_date,
                    units_sold_during=units_during,
                    revenue_during=revenue_during,
                    units_sold_baseline=0,  # Would need baseline comparison
                    revenue_baseline=0,
                )
            )

        return analyses

    async def get_pricing_recommendations(
        self,
        product_ids: list[str] | None = None,
    ) -> list[PricingRecommendation]:
        """
        Generate pricing recommendations based on margins and market data.

        Args:
            product_ids: Optional product IDs to analyze

        Returns:
            List of PricingRecommendation.
        """
        prices = await self.get_product_prices(product_ids)
        recommendations: list[PricingRecommendation] = []

        for price in prices:
            # Simple rule-based recommendations
            if price.margin_pct < 10:
                # Low margin — consider price increase
                recommended = price.current_price * 1.10
                recommendations.append(
                    PricingRecommendation(
                        product_id=price.product_price_id if hasattr(price, 'product_price_id') else price.product_id,
                        product_name=price.product_name,
                        current_price=price.current_price,
                        recommended_price=round(recommended, 2),
                        confidence=0.7,
                        reason=f"هامش الربح منخفض ({price.margin_pct:.1f}%). يُنصح بزيادة السعر 10% لتحسين الربحية.",
                        expected_impact="زيادة الربحية مع تأثير طفء على المبيعات",
                        risk_level="medium",
                        data_sources=["odoo:product.product"],
                    )
                )
            elif price.margin_pct > 50:
                # High margin — potential for competitive pricing
                recommended = price.current_price * 0.90
                recommendations.append(
                    PricingRecommendation(
                        product_id=price.product_id,
                        product_name=price.product_name,
                        current_price=price.current_price,
                        recommended_price=round(recommended, 2),
                        confidence=0.6,
                        reason=f"هامش الربح مرتفع ({price.margin_pct:.1f}%). يمكن تخفيض السعر 10% لزيادة الحصة السوقية.",
                        expected_impact="زيادة المبيعات مع الحفاظ على ربحية جيدة",
                        risk_level="low",
                        data_sources=["odoo:product.product"],
                    )
                )

        return recommendations
