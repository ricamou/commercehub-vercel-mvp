from app.core.config import settings


class PricingService:
    def calculate_sale_price(
        self,
        cost_price: float,
        margin_percent: float | None = None,
        ml_commission_percent: float | None = None,
        fixed_operational_cost: float | None = None
    ) -> dict:
        margin = margin_percent if margin_percent is not None else settings.DEFAULT_MARGIN_PERCENT
        commission_percent = (
            ml_commission_percent
            if ml_commission_percent is not None
            else settings.ML_COMMISSION_PERCENT
        )
        fixed_cost = (
            fixed_operational_cost
            if fixed_operational_cost is not None
            else settings.FIXED_OPERATIONAL_COST
        )

        target_profit = cost_price * (margin / 100)
        gross_price = (cost_price + fixed_cost + target_profit) / (1 - commission_percent / 100)

        sale_price = self._round_price(gross_price)
        estimated_commission = round(sale_price * (commission_percent / 100), 2)
        estimated_profit = round(sale_price - estimated_commission - fixed_cost - cost_price, 2)

        return {
            "cost_price": round(cost_price, 2),
            "sale_price": sale_price,
            "margin_percent": margin,
            "ml_commission_percent": commission_percent,
            "estimated_ml_commission": estimated_commission,
            "fixed_operational_cost": round(fixed_cost, 2),
            "estimated_profit": estimated_profit
        }

    def _round_price(self, price: float) -> float:
        rounded = int(price) + 0.90
        if rounded < price:
            rounded += 1
        return round(rounded, 2)
