from modules.ai.service import enrich, optimize_listing

def listing_payload(product, category_id="MLBXXXX"):
    enriched = optimize_listing(product)
    return {
        "title": enriched["title"],
        "category_id": category_id or "MLBXXXX",
        "price": product["sale_price"],
        "currency_id": "BRL",
        "available_quantity": product["stock"],
        "buying_mode": "buy_it_now",
        "listing_type_id": "gold_special",
        "condition": "new",
        "seller_custom_field": product["sku"],
        "pictures": [{"source": "https://via.placeholder.com/800"}],
        "attributes": [
            {"id": "BRAND", "value_name": product["brand"]},
            {"id": "GTIN", "value_name": product["ean"]}
        ],
        "description": enriched["description"]
    }