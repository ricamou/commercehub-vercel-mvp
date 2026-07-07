import re
from config import settings

def round_price(price):
    rounded = int(price) + 0.90
    if rounded < price:
        rounded += 1
    return round(rounded, 2)

def calculate_price(cost_price, margin_percent=None, commission_percent=None, fixed_cost=None):
    cost_price = float(cost_price or 0)
    margin_percent = settings.DEFAULT_MARGIN_PERCENT if margin_percent is None else float(margin_percent)
    commission_percent = settings.ML_COMMISSION_PERCENT if commission_percent is None else float(commission_percent)
    fixed_cost = settings.FIXED_OPERATIONAL_COST if fixed_cost is None else float(fixed_cost)
    desired_profit = cost_price * margin_percent / 100
    variable_fee = commission_percent / 100
    if variable_fee >= 1:
        return {"success": False, "message": "Comissão inválida."}
    sale_price = round_price((cost_price + fixed_cost + desired_profit) / (1 - variable_fee))
    commission = sale_price * variable_fee
    profit = sale_price - cost_price - fixed_cost - commission
    margin_real = (profit / sale_price * 100) if sale_price else 0
    return {
        "success": True,
        "cost_price": round(cost_price, 2),
        "sale_price": sale_price,
        "commission": round(commission, 2),
        "fixed_cost": round(fixed_cost, 2),
        "profit": round(profit, 2),
        "margin_percent": round(margin_real, 2),
        "status": "healthy" if profit > 0 and margin_real >= 18 else "attention"
    }

def clean(text):
    return re.sub(r"\s+", " ", str(text or "").strip())

def ai_enrich(product):
    name = clean(product.get("name"))
    brand = clean(product.get("brand"))
    category = clean(product.get("category") or product.get("internal_category"))
    title_parts = []
    if brand and brand.lower() not in name.lower():
        title_parts.append(brand)
    title_parts.append(name)
    if category and category.lower() not in name.lower():
        title_parts.append(category)
    title = clean(" ".join(title_parts))[:60]
    description = "\n".join([
        f"- Produto: {name}",
        f"- Marca: {brand or 'Não informada'}",
        f"- Categoria: {category or 'Não informada'}",
        f"- EAN/GTIN: {clean(product.get('ean')) or 'Não informado'}",
        "- Produto novo e pronto para venda conforme disponibilidade de estoque."
    ])
    text = f"{name} {brand} {category}".lower()
    words = re.findall(r"[a-zA-ZÀ-ÿ0-9]+", text)
    stop = {"de", "da", "do", "para", "com", "e", "a", "o", "em", "um", "uma"}
    keywords = []
    for word in words:
        if len(word) > 2 and word not in stop and word not in keywords:
            keywords.append(word)
    return {
        "title": title,
        "description": description,
        "keywords": keywords[:12],
        "category_search": suggest_category_search(product),
        "seo_score": 100 if len(title) >= 20 and len(keywords) >= 3 else 70,
    }

def suggest_category_search(product):
    name = clean(product.get("name")).lower()
    category = clean(product.get("category") or product.get("internal_category")).lower()
    if "suporte" in name and "celular" in name: return "suporte celular carro"
    if "cabo" in name and "usb" in name: return "cabo usb c"
    if "microfibra" in name: return "pano microfibra limpeza"
    if "tapete" in name and "pet" in category: return "tapete higienico pet"
    if "organizador" in name: return "organizador cozinha"
    return clean(f"{name} {category}")

def stock_status(stock):
    stock = int(stock or 0)
    if stock <= 0: return "out_of_stock"
    if stock <= 3: return "low_stock"
    return "available"

def build_listing_payload(product, category_id):
    enriched = ai_enrich(product)
    return {
        "title": enriched["title"],
        "category_id": category_id or product.get("ml_category_id") or "",
        "price": float(product.get("sale_price") or 0),
        "currency_id": "BRL",
        "available_quantity": int(product.get("stock") or 0),
        "buying_mode": "buy_it_now",
        "listing_type_id": "gold_special",
        "condition": "new",
        "seller_custom_field": product.get("sku"),
        "pictures": [{"source": product.get("image_url") or "https://via.placeholder.com/800"}],
        "attributes": [
            {"id": "BRAND", "value_name": product.get("brand") or "Genérico"},
            {"id": "GTIN", "value_name": product.get("ean") or ""},
        ],
    }

def product_profit(product):
    sale = float(product.get("sale_price") or 0)
    cost = float(product.get("cost_price") or 0)
    fee = sale * (settings.ML_COMMISSION_PERCENT / 100)
    fixed = settings.FIXED_OPERATIONAL_COST
    profit = sale - cost - fee - fixed
    margin = (profit / sale * 100) if sale else 0
    return {"sku": product.get("sku"), "name": product.get("name"), "profit": round(profit, 2), "margin": round(margin, 2)}
