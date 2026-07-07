from modules.database import service as database


async def save_pricing_event(payload: dict):
    event = {
        "event_type": "pricing_update",
        "message": "Preço calculado/atualizado",
        "payload": payload
    }

    if database.status()["supabase_configured"]:
        return await database.insert("events", event)

    return {
        "success": True,
        "source": "memory_demo",
        "message": "Evento de preço recebido. Configure Supabase para persistir.",
        "event": event
    }