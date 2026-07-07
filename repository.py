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


async def category_attributes(category_id):
    if not httpx:
        return {"success": False, "message": "httpx não instalado"}
    headers = {"Authorization": f"Bearer {config.ML_ACCESS_TOKEN}"} if config.ML_ACCESS_TOKEN else {}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"https://api.mercadolibre.com/categories/{category_id}/attributes", headers=headers)
        return {"success": r.status_code < 400, "status_code": r.status_code, "data": r.json() if r.content else []}


async def publish_item(payload):
    if not config.ML_ACCESS_TOKEN:
        return {"success": False, "message": "ML_ACCESS_TOKEN não configurado"}
    if not httpx:
        return {"success": False, "message": "httpx não instalado"}

    headers = {
        "Authorization": f"Bearer {config.ML_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("https://api.mercadolibre.com/items", headers=headers, json=payload)
        return {
            "success": r.status_code < 400,
            "status_code": r.status_code,
            "data": r.json() if r.content else {},
            "payload_sent": payload
        }


async def pause_item(item_id):
    if not config.ML_ACCESS_TOKEN:
        return {"success": False, "message": "ML_ACCESS_TOKEN não configurado"}
    headers = {"Authorization": f"Bearer {config.ML_ACCESS_TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.put(f"https://api.mercadolibre.com/items/{item_id}", headers=headers, json={"status": "paused"})
        return {"success": r.status_code < 400, "status_code": r.status_code, "data": r.json() if r.content else {}}


async def update_item_price_stock(item_id, price=None, stock=None):
    if not config.ML_ACCESS_TOKEN:
        return {"success": False, "message": "ML_ACCESS_TOKEN não configurado"}

    payload = {}
    if price is not None:
        payload["price"] = float(price)
    if stock is not None:
        payload["available_quantity"] = int(stock)

    headers = {"Authorization": f"Bearer {config.ML_ACCESS_TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.put(f"https://api.mercadolibre.com/items/{item_id}", headers=headers, json=payload)
        return {"success": r.status_code < 400, "status_code": r.status_code, "data": r.json() if r.content else {}, "payload_sent": payload}
