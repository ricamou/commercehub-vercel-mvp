from modules.products.service import all_products, with_price
from modules.database import service as database
import uuid
from datetime import datetime


async def list_products():
    if database.status()["supabase_configured"]:
        result = await database.select("products")
        if result.get("success"):
            return {"success": True, "source": "supabase", "products": result.get("data", [])}
        return {"success": False, "source": "supabase", "message": result.get("message"), "products": []}

    return {"success": True, "source": "memory_demo", "products": all_products()}


async def get_product(product_id: str):
    if database.status()["supabase_configured"]:
        result = await database.select(f"products?id=eq.{product_id}")
        data = result.get("data", [])
        return {"success": bool(data), "source": "supabase", "product": data[0] if data else None}

    product = next((p for p in all_products() if p.get("sku") == product_id or p.get("id") == product_id), None)
    return {"success": bool(product), "source": "memory_demo", "product": product}


async def create_product(payload: dict):
    product = normalize_product(payload)

    if database.status()["supabase_configured"]:
        return await database.insert("products", product)

    return {
        "success": True,
        "source": "memory_demo",
        "message": "Produto recebido. Configure Supabase para persistir.",
        "product": product
    }


async def update_product(product_id: str, payload: dict):
    product = normalize_product(payload)
    product["updated_at"] = datetime.utcnow().isoformat()

    if database.status()["supabase_configured"]:
        return await database.patch("products", product_id, product)

    return {
        "success": True,
        "source": "memory_demo",
        "message": "Update simulado. Configure Supabase para persistir.",
        "product_id": product_id,
        "product": product
    }


async def delete_product(product_id: str):
    if database.status()["supabase_configured"]:
        return await database.delete("products", product_id)

    return {
        "success": True,
        "source": "memory_demo",
        "message": "Delete simulado. Configure Supabase para persistir.",
        "product_id": product_id
    }


def normalize_product(payload: dict):
    product = {
        "sku": str(payload.get("sku", "")).strip(),
        "name": str(payload.get("name", "")).strip(),
        "brand": str(payload.get("brand", "")).strip(),
        "ean": str(payload.get("ean", "")).strip(),
        "category": str(payload.get("category", "")).strip(),
        "description": str(payload.get("description", "")).strip(),
        "cost_price": float(payload.get("cost_price") or 0),
        "sale_price": float(payload.get("sale_price") or 0),
        "stock": int(payload.get("stock") or 0),
        "status": payload.get("status", "active"),
        "raw_data": payload.get("raw_data", {})
    }

    if product["cost_price"] and not product["sale_price"]:
        priced = with_price(product)
        product["sale_price"] = priced.get("sale_price", 0)

    return product