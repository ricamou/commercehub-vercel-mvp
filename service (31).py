from core import config

try:
    import httpx
except Exception:
    httpx = None


def status():
    configured = bool(getattr(config, "SUPABASE_URL", "") and getattr(config, "SUPABASE_SERVICE_ROLE_KEY", ""))
    return {
        "supabase_configured": configured,
        "mode": "supabase_ready" if configured else "memory_demo",
        "message": "Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY na Vercel para persistência real."
    }


def headers():
    return {
        "apikey": config.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }


async def select(table: str):
    if not status()["supabase_configured"] or not httpx:
        return {"success": False, "message": "Supabase não configurado.", "data": []}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{config.SUPABASE_URL}/rest/v1/{table}?select=*",
            headers=headers()
        )
        return {
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "data": response.json() if response.content else []
        }


async def insert(table: str, payload: dict):
    if not status()["supabase_configured"] or not httpx:
        return {"success": False, "message": "Supabase não configurado.", "data": None}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{config.SUPABASE_URL}/rest/v1/{table}",
            headers=headers(),
            json=payload
        )
        return {
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "data": response.json() if response.content else None
        }


async def upsert(table: str, payload: dict, conflict: str = "id"):
    if not status()["supabase_configured"] or not httpx:
        return {"success": False, "message": "Supabase não configurado.", "data": None}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{config.SUPABASE_URL}/rest/v1/{table}?on_conflict={conflict}",
            headers={**headers(), "Prefer": "resolution=merge-duplicates,return=representation"},
            json=payload
        )
        return {
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "data": response.json() if response.content else None
        }


async def health_check():
    if not status()["supabase_configured"]:
        return status()

    result = await select("companies")
    return {
        "supabase_configured": True,
        "mode": "supabase_ready",
        "connection_ok": result.get("success", False),
        "status_code": result.get("status_code"),
        "message": "Conexão testada na tabela companies."
    }


async def patch(table: str, row_id: str, payload: dict):
    if not status()["supabase_configured"] or not httpx:
        return {"success": False, "message": "Supabase não configurado.", "data": None}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.patch(
            f"{config.SUPABASE_URL}/rest/v1/{table}?id=eq.{row_id}",
            headers=headers(),
            json=payload
        )
        return {
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "data": response.json() if response.content else None
        }


async def delete(table: str, row_id: str):
    if not status()["supabase_configured"] or not httpx:
        return {"success": False, "message": "Supabase não configurado.", "data": None}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.delete(
            f"{config.SUPABASE_URL}/rest/v1/{table}?id=eq.{row_id}",
            headers=headers()
        )
        return {
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "deleted": response.status_code < 400
        }
