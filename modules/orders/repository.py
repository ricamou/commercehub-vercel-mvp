from modules.orders.service import simulate_order
from modules.database import service as database


async def list_orders():
    if database.status()["supabase_configured"]:
        result = await database.select("orders")
        if result.get("success"):
            return {"success": True, "source": "supabase", "orders": result.get("data", [])}

    return {"success": True, "source": "memory_demo", "orders": [simulate_order()]}


async def save_order(order: dict):
    if database.status()["supabase_configured"]:
        return await database.insert("orders", order)

    return {
        "success": True,
        "source": "memory_demo",
        "message": "Pedido recebido. Configure Supabase para persistir.",
        "order": order
    }


async def save_event(event: dict):
    if database.status()["supabase_configured"]:
        return await database.insert("events", event)

    return {
        "success": True,
        "source": "memory_demo",
        "message": "Evento recebido. Configure Supabase para persistir.",
        "event": event
    }