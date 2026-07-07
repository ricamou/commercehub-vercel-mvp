from modules.database import service as database


async def save_inventory_event(payload: dict):
    event = {
        "event_type": "inventory_sync",
        "message": "Sincronização de estoque executada",
        "payload": payload
    }

    if database.status()["supabase_configured"]:
        return await database.insert("events", event)

    return {
        "success": True,
        "source": "memory_demo",
        "message": "Evento de estoque recebido. Configure Supabase para persistir.",
        "event": event
    }