from modules.database import service as database


async def save_ai_event(payload: dict):
    event = {
        "event_type": "ai_listing_optimizer",
        "message": "Anúncio otimizado por IA",
        "payload": payload
    }

    if database.status()["supabase_configured"]:
        return await database.insert("events", event)

    return {
        "success": True,
        "source": "memory_demo",
        "message": "Evento de IA recebido. Configure Supabase para persistir.",
        "event": event
    }