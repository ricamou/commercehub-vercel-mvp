from urllib.parse import urlencode
from core import config

try:
    import httpx
except Exception:
    httpx = None

def status():
    return {
        "client_id": bool(config.ML_CLIENT_ID),
        "client_secret": bool(config.ML_CLIENT_SECRET),
        "redirect_uri": config.ML_REDIRECT_URI,
        "access_token": bool(config.ML_ACCESS_TOKEN),
        "refresh_token": bool(config.ML_REFRESH_TOKEN),
        "user_id": config.ML_USER_ID or None
    }

def auth_url():
    if not config.ML_CLIENT_ID or not config.ML_REDIRECT_URI:
        return ""
    return "https://auth.mercadolivre.com.br/authorization?" + urlencode({
        "response_type": "code",
        "client_id": config.ML_CLIENT_ID,
        "redirect_uri": config.ML_REDIRECT_URI
    })

async def exchange_code(code):
    if not httpx:
        return {"success": False, "message": "httpx não instalado"}
    payload = {
        "grant_type": "authorization_code",
        "client_id": config.ML_CLIENT_ID,
        "client_secret": config.ML_CLIENT_SECRET,
        "code": code,
        "redirect_uri": config.ML_REDIRECT_URI
    }
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("https://api.mercadolibre.com/oauth/token", data=payload)
        try:
            data = r.json()
        except Exception:
            data = {"text": r.text}
    return {"success": r.status_code < 400, "status_code": r.status_code, "data": data}

async def me():
    if not config.ML_ACCESS_TOKEN:
        return {"success": False, "message": "ML_ACCESS_TOKEN não configurado"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://api.mercadolibre.com/users/me", headers={"Authorization": f"Bearer {config.ML_ACCESS_TOKEN}"})
        return {"success": r.status_code < 400, "status_code": r.status_code, "data": r.json() if r.content else {}}

async def categories(q):
    headers = {"Authorization": f"Bearer {config.ML_ACCESS_TOKEN}"} if config.ML_ACCESS_TOKEN else {}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://api.mercadolibre.com/sites/MLB/domain_discovery/search", params={"q": q}, headers=headers)
        return {"success": r.status_code < 400, "status_code": r.status_code, "data": r.json() if r.content else []}