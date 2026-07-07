from modules.database import service as database


async def save_listing(record: dict):
    if database.status()["supabase_configured"]:
        return await database.insert("listings", record)

    return {
        "success": True,
        "source": "memory_demo",
        "message": "Listing recebido. Configure Supabase para persistir.",
        "listing": record
    }