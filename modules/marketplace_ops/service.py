from modules.products.service import product_by_sku
from modules.listings.service import listing_payload
from modules.pricing.service import ml_price_payload
from modules.inventory.service import stock_update_payload


def operations_plan():
    return {
        "success": True,
        "steps": [
            "Criar preview do anúncio",
            "Publicar no Mercado Livre",
            "Salvar external_id do anúncio",
            "Atualizar preço via Pricing Automation",
            "Atualizar estoque via Inventory Sync",
            "Pausar anúncio quando necessário",
            "Registrar eventos no Supabase"
        ]
    }


def listing_operation_preview(sku: str, category_id: str):
    product = product_by_sku(sku)
    if not product:
        return {"success": False, "message": "Produto não encontrado."}

    return {
        "success": True,
        "sku": sku,
        "category_id": category_id,
        "listing_payload": listing_payload(product, category_id),
        "price_payload": ml_price_payload(sku),
        "stock_payload": stock_update_payload(sku, product.get("stock", 0)),
        "next_actions": [
            "Validar categoria",
            "Validar atributos obrigatórios",
            "Publicar anúncio",
            "Salvar ID externo",
            "Ativar sincronização"
        ]
    }


def status():
    return {
        "success": True,
        "module": "Marketplace Operations",
        "marketplaces": [
            {"key": "mercado_livre", "status": "active"},
            {"key": "shopee", "status": "planned"},
            {"key": "amazon", "status": "planned"},
            {"key": "magalu", "status": "planned"}
        ],
        "features": [
            "publish",
            "pause",
            "update_price",
            "update_stock",
            "save_listing",
            "operations_preview"
        ]
    }