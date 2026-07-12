from api.core.config import SUPABASE_URL, SUPABASE_KEY
from api.core.http_client import async_request_json

MEMORY = {"companies": [], "users": [], "oauth_tokens": [], "logs": []}

def configured():
    return bool(SUPABASE_URL and SUPABASE_KEY)

def mode():
    return "supabase" if configured() else "memory"

def headers(prefer="return=representation"):
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }

async def rest(method, path, payload=None, prefer="return=representation"):
    if not configured():
        return {"success": False, "mode": "memory", "status_code": 0, "data": [], "error": "Supabase não configurado", "transport": "memory"}

    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{path.lstrip('/')}"
    res = await async_request_json(method, url, headers(prefer), payload, 15)
    res["mode"] = "supabase"
    return res

async def select(table, query="select=*"):
    if not configured():
        return {"success": True, "mode": "memory", "data": MEMORY.get(table, []), "transport": "memory"}

    res = await rest("GET", f"{table}?{query}")
    if not isinstance(res.get("data"), list):
        res["data"] = []
    return res

async def upsert(table, payload, conflict="id"):
    if not configured():
        values = payload if isinstance(payload, list) else [payload]
        items = MEMORY.setdefault(table, [])
        for value in values:
            found = False
            for i, item in enumerate(items):
                if str(item.get(conflict)) == str(value.get(conflict)):
                    items[i] = {**item, **value}
                    found = True
                    break
            if not found:
                items.append(value)
        return {"success": True, "mode": "memory", "data": payload, "transport": "memory"}

    return await rest("POST", f"{table}?on_conflict={conflict}", payload, "resolution=merge-duplicates,return=representation")

async def insert(table, payload):
    if not configured():
        MEMORY.setdefault(table, []).append(payload)
        return {"success": True, "mode": "memory", "data": payload, "transport": "memory"}
    return await rest("POST", table, payload)

async def delete(table, query):
    if not configured():
        return {"success": True, "mode": "memory", "data": [], "transport": "memory"}
    return await rest("DELETE", f"{table}?{query}", None, "return=representation")


async def update(table, query, payload):
    if not configured():
        items = MEMORY.setdefault(table, [])
        updated = []
        for i, item in enumerate(items):
            match = True
            for part in str(query or "").split("&"):
                if "=eq." in part:
                    key, value = part.split("=eq.", 1)
                    if str(item.get(key)) != str(value):
                        match = False
                        break
            if match:
                items[i] = {**item, **payload}
                updated.append(items[i])
        return {"success": True, "mode": "memory", "data": updated, "transport": "memory"}
    return await rest("PATCH", f"{table}?{query}", payload)
