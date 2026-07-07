from app.services.pricing_service import PricingService


def test_calculate_sale_price_returns_valid_price():
    service = PricingService()
    result = service.calculate_sale_price(cost_price=100, margin_percent=30)

    assert result["sale_price"] > 100
    assert result["estimated_profit"] > 0
    assert result["margin_percent"] == 30
