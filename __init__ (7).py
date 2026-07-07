from modules.suppliers.service import suppliers, supplier_products
from modules.database import service as database


async def list_suppliers():
    if database.status()["supabase_configured"]:
        result = await database.select("suppliers")
        if result.get("success"):
            return {"success": True, "source": "supabase", "suppliers": result.get("data", [])}

    return {"success": True, "source": "memory_demo", "suppliers": suppliers()}


async def get_supplier(supplier_id: str):
    if database.status()["supabase_configured"]:
        result = await database.select(f"suppliers?id=eq.{supplier_id}")
        data = result.get("data", [])
        return {"success": bool(data), "source": "supabase", "supplier": data[0] if data else None}

    supplier = next((s for s in suppliers() if s.get("id") == supplier_id), None)
    return {"success": bool(supplier), "source": "memory_demo", "supplier": supplier}


async def create_supplier(payload: dict):
    supplier = normalize_supplier(payload)

    if database.status()["supabase_configured"]:
        return await database.insert("suppliers", supplier)

    return {
        "success": True,
        "source": "memory_demo",
        "message": "Fornecedor recebido. Configure Supabase para persistir.",
        "supplier": supplier
    }


async def update_supplier(supplier_id: str, payload: dict):
    supplier = normalize_supplier(payload)

    if database.status()["supabase_configured"]:
        return await database.patch("suppliers", supplier_id, supplier)

    return {
        "success": True,
        "source": "memory_demo",
        "message": "Update simulado. Configure Supabase para persistir.",
        "supplier_id": supplier_id,
        "supplier": supplier
    }


async def delete_supplier(supplier_id: str):
    if database.status()["supabase_configured"]:
        return await database.delete("suppliers", supplier_id)

    return {
        "success": True,
        "source": "memory_demo",
        "message": "Delete simulado. Configure Supabase para persistir.",
        "supplier_id": supplier_id
    }


async def list_supplier_products():
    if database.status()["supabase_configured"]:
        result = await database.select("products")
        if result.get("success"):
            return {"success": True, "source": "supabase", "products": result.get("data", [])}

    return {"success": True, "source": "memory_demo", "products": supplier_products()}


def normalize_supplier(payload: dict):
    return {
        "name": str(payload.get("name", "")).strip(),
        "type": str(payload.get("type", "manual")).strip(),
        "status": str(payload.get("status", "active")).strip(),
        "config": payload.get("config", {})
    }