from modules.products.service import all_products, stock_status
from modules.suppliers.service import supplier_products


def inventory_report():
    products = all_products()
    return {
        "success": True,
        "count": len(products),
        "total_stock": sum(int(p.get("stock") or 0) for p in products),
        "products": [
            {
                "sku": p.get("sku"),
                "name": p.get("name"),
                "stock": int(p.get("stock") or 0),
                "status": stock_status(p.get("stock")),
                "sale_price": p.get("sale_price"),
                "cost_price": p.get("cost_price")
            }
            for p in products
        ]
    }


def supplier_stock_preview():
    products = supplier_products()
    return {
        "success": True,
        "source": "mock_supplier",
        "products": [
            {
                "sku": p.get("sku"),
                "name": p.get("name"),
                "supplier_stock": int(p.get("stock") or 0),
                "sync_action": "update_catalog_stock",
                "marketplace_action": "update_listing_stock"
            }
            for p in products
        ]
    }


def stock_update_payload(sku: str, stock: int, marketplace_item_id: str = ""):
    return {
        "sku": sku,
        "marketplace": "mercado_livre",
        "marketplace_item_id": marketplace_item_id,
        "available_quantity": max(int(stock or 0), 0),
        "action": "update_available_quantity"
    }


def sync_plan():
    return {
        "success": True,
        "steps": [
            "Ler estoque do fornecedor",
            "Normalizar por SKU",
            "Comparar com catálogo",
            "Atualizar estoque interno",
            "Gerar payload para Mercado Livre",
            "Enviar atualização ao anúncio",
            "Registrar evento de sincronização"
        ]
    }