from core import config
from modules.products.service import all_products, product_by_sku


def calculate_price(cost_price, margin_percent=None, commission_percent=None, fixed_cost=None):
    cost_price = float(cost_price or 0)
    margin_percent = float(margin_percent if margin_percent is not None else config.DEFAULT_MARGIN_PERCENT)
    commission_percent = float(commission_percent if commission_percent is not None else config.ML_COMMISSION_PERCENT)
    fixed_cost = float(fixed_cost if fixed_cost is not None else config.FIXED_OPERATIONAL_COST)

    desired_profit = cost_price * margin_percent / 100
    variable_fee = commission_percent / 100

    if variable_fee >= 1:
        return {"success": False, "message": "Comissão inválida."}

    sale_price = (cost_price + fixed_cost + desired_profit) / (1 - variable_fee)
    rounded = int(sale_price) + 0.90
    if rounded < sale_price:
        rounded += 1

    commission = rounded * variable_fee
    profit = rounded - cost_price - fixed_cost - commission
    real_margin = (profit / rounded * 100) if rounded else 0

    return {
        "success": True,
        "cost_price": round(cost_price, 2),
        "sale_price": round(rounded, 2),
        "commission": round(commission, 2),
        "fixed_cost": round(fixed_cost, 2),
        "profit": round(profit, 2),
        "margin_percent": round(real_margin, 2),
        "recommendation": recommendation(profit, real_margin)
    }


def recommendation(profit, margin_percent):
    if profit <= 0:
        return "not_profitable"
    if margin_percent < 8:
        return "critical_margin"
    if margin_percent < 18:
        return "low_margin"
    return "healthy"


def product_pricing(sku, margin_percent=None):
    product = product_by_sku(sku)
    if not product:
        return {"success": False, "message": "Produto não encontrado."}

    pricing = calculate_price(product.get("cost_price"), margin_percent=margin_percent)
    return {"success": True, "product": product, "pricing": pricing}


def pricing_report(margin_percent=None):
    products = all_products()
    return {
        "success": True,
        "count": len(products),
        "products": [
            {
                "sku": p.get("sku"),
                "name": p.get("name"),
                "cost_price": p.get("cost_price"),
                "current_sale_price": p.get("sale_price"),
                "suggested": calculate_price(p.get("cost_price"), margin_percent=margin_percent)
            }
            for p in products
        ]
    }


def ml_price_payload(sku, margin_percent=None, marketplace_item_id=""):
    result = product_pricing(sku, margin_percent=margin_percent)
    if not result.get("success"):
        return result

    return {
        "success": True,
        "payload": {
            "sku": sku,
            "marketplace": "mercado_livre",
            "marketplace_item_id": marketplace_item_id,
            "price": result["pricing"]["sale_price"],
            "action": "update_price"
        },
        "pricing": result["pricing"]
    }