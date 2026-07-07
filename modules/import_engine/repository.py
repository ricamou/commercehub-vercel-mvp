from modules.database import service as database


async def save_import_event(payload: dict):
    event = {
        "event_type": "supplier_import",
        "message": "Importação de fornecedor executada",
        "payload": payload
    }

    if database.status()["supabase_configured"]:
        return await database.insert("events", event)

    return {
        "success": True,
        "source": "memory_demo",
        "message": "Evento de importação recebido. Configure Supabase para persistir.",
        "event": event
    }


async def persist_imported_products(products: list[dict]):
    results = []

    if database.status()["supabase_configured"]:
        for product in products:
            result = await database.insert("products", product)
            results.append(result)

        return {
            "success": True,
            "source": "supabase",
            "imported_count": len(results),
            "results": results
        }

    return {
        "success": True,
        "source": "memory_demo",
        "message": "Produtos normalizados, mas não persistidos. Configure Supabase para salvar.",
        "imported_count": len(products),
        "products": products
    }