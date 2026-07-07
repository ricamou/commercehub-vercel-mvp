from core import config

def calculate_price(cost_price):
    cost_price = float(cost_price or 0)
    desired_profit = cost_price * config.DEFAULT_MARGIN_PERCENT / 100
    variable_fee = config.ML_COMMISSION_PERCENT / 100
    sale_price = (cost_price + config.FIXED_OPERATIONAL_COST + desired_profit) / (1 - variable_fee)
    rounded = int(sale_price) + 0.90
    if rounded < sale_price:
        rounded += 1
    commission = rounded * variable_fee
    profit = rounded - cost_price - config.FIXED_OPERATIONAL_COST - commission
    margin = (profit / rounded * 100) if rounded else 0
    return {
        "sale_price": round(rounded, 2),
        "commission": round(commission, 2),
        "profit": round(profit, 2),
        "margin_percent": round(margin, 2),
        "status": "healthy" if profit > 0 and margin >= 18 else "attention"
    }

def with_price(product):
    return {**product, **calculate_price(product.get("cost_price", 0))}

def stock_status(stock):
    stock = int(stock or 0)
    if stock <= 0:
        return "out_of_stock"
    if stock <= 3:
        return "low_stock"
    return "available"

def all_products():
    from modules.suppliers.service import MOCK_PRODUCTS
    return [with_price(p) for p in MOCK_PRODUCTS]