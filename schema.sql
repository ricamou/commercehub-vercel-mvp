from modules.database import service as database


async def save_operation_event(payload: dict):
    event = {
        "event_type": "marketplace_operation",
        "message": "Operação de marketplace executada",
        "payload": payload
    }

    if database.status()["supabase_configured"]:
        return await database.insert("events", event)

    return {
        "success": True,
        "source": "memory_demo",
        "message": "Evento de marketplace recebido. Configure Supabase para persistir.",
        "event": event
    }