from modules.products.service import all_products
from modules.suppliers.service import suppliers
from modules.mercadolivre import service as ml
from modules.database import service as database

def enterprise_summary():
    products = all_products()
    total_stock = sum(int(p.get("stock") or 0) for p in products)
    total_cost = sum(float(p.get("cost_price") or 0) * int(p.get("stock") or 0) for p in products)
    total_profit = sum(float(p.get("profit") or 0) * int(p.get("stock") or 0) for p in products)

    return {
        "success": True,
        "kpis": {
            "products": len(products),
            "suppliers": len(suppliers()),
            "stock_total": total_stock,
            "stock_cost": round(total_cost, 2),
            "profit_potential": round(total_profit, 2),
            "mercado_livre_connected": ml.status().get("access_token"),
            "database_mode": database.status().get("mode")
        },
        "alerts": [
            "Configure Supabase para persistência real." if database.status().get("mode") == "memory_demo" else "Banco persistente ativo.",
            "Revise categorias antes de publicação real no Mercado Livre.",
            "Configure rotina de sync quando conectar fornecedores reais."
        ]
    }