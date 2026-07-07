from modules.suppliers.service import supplier_products
from modules.universal_connector.service import normalize_supplier_product, parse_payload_by_type, validate_product
from modules.products.service import with_price


def import_preview():
    products = supplier_products()
    normalized = [with_price(normalize_supplier_product(p, "mock_supplier")) for p in products]
    return {
        "success": True,
        "source": "mock_supplier",
        "count": len(normalized),
        "products": normalized,
        "validation": [validate_product(p) for p in normalized]
    }


def import_from_payload(source_type, payload):
    parsed = parse_payload_by_type(source_type, payload)
    products = [with_price(product) for product in parsed.get("products", [])]

    valid_products = []
    invalid_products = []

    for product in products:
        validation = validate_product(product)
        if validation.get("valid"):
            valid_products.append(product)
        else:
            invalid_products.append({
                "product": product,
                "validation": validation
            })

    return {
        "success": True,
        "source_type": source_type,
        "count": len(products),
        "valid_count": len(valid_products),
        "invalid_count": len(invalid_products),
        "products": products,
        "valid_products": valid_products,
        "invalid_products": invalid_products,
        "validation": parsed.get("validation", [])
    }


def build_import_summary(source_type: str, products: list[dict]):
    total_stock = sum(int(p.get("stock") or 0) for p in products)
    total_cost = sum(float(p.get("cost_price") or 0) * int(p.get("stock") or 0) for p in products)

    return {
        "source_type": source_type,
        "products_count": len(products),
        "total_stock": total_stock,
        "total_cost": round(total_cost, 2),
        "ready_to_persist": len(products) > 0
    }


def import_plan():
    return {
        "success": True,
        "steps": [
            "Receber dados reais do fornecedor",
            "Detectar formato: API, JSON, XML ou CSV",
            "Normalizar campos para padrão CommerceHub",
            "Validar SKU e nome",
            "Aplicar precificação",
            "Separar válidos e inválidos",
            "Salvar produtos válidos no Supabase",
            "Registrar evento de importação"
        ]
    }