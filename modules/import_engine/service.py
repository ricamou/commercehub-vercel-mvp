from modules.suppliers.service import supplier_products
from modules.universal_connector.service import normalize_supplier_product, parse_payload_by_type
from modules.products.service import with_price

def import_preview():
    products = supplier_products()
    normalized = [with_price(normalize_supplier_product(p, "mock_supplier")) for p in products]
    return {"success": True, "source": "mock_supplier", "count": len(normalized), "products": normalized}

def import_from_payload(source_type, payload):
    parsed = parse_payload_by_type(source_type, payload)
    products = [with_price(product) for product in parsed.get("products", [])]
    return {"success": True, "source_type": source_type, "count": len(products), "products": products, "validation": parsed.get("validation", [])}

def import_plan():
    return {"success": True, "steps": ["Receber dados", "Detectar formato", "Normalizar", "Validar", "Precificar", "Enviar ao catálogo"]}