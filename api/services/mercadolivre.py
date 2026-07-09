from urllib.parse import urlencode
from datetime import datetime
from api.core.config import ML_CLIENT_ID, ML_CLIENT_SECRET, ML_REDIRECT_URI, DEFAULT_COMPANY_ID
from api.core.http_client import request_json
from api.db import store

def auth_url():
    if not ML_CLIENT_ID:
        return ""
    return "https://auth.mercadolivre.com.br/authorization?" + urlencode({"response_type": "code", "client_id": ML_CLIENT_ID, "redirect_uri": ML_REDIRECT_URI})

async def get_token():
    result = await store.select("oauth_tokens", "select=*&marketplace=eq.mercado_livre&limit=1")
    rows = result.get("data") or []
    return rows[0] if rows else {}

async def save_token(token):
    payload = {"id": "mercado_livre_default", "company_id": DEFAULT_COMPANY_ID, "marketplace": "mercado_livre", "access_token": token.get("access_token"), "refresh_token": token.get("refresh_token"), "user_id": str(token.get("user_id") or ""), "expires_in": int(token.get("expires_in") or 0), "token_type": token.get("token_type") or "Bearer", "scope": token.get("scope") or "", "updated_at": datetime.utcnow().isoformat()}
    return await store.upsert("oauth_tokens", payload, "id")

async def exchange_code(code):
    result = request_json("POST", "https://api.mercadolibre.com/oauth/token", {"Content-Type": "application/json"}, {"grant_type": "authorization_code", "client_id": ML_CLIENT_ID, "client_secret": ML_CLIENT_SECRET, "code": code, "redirect_uri": ML_REDIRECT_URI}, 12)
    if result.get("success"):
        await save_token(result.get("data") or {})
    return result

async def refresh_token():
    token = await get_token()
    refresh = token.get("refresh_token")
    if not refresh:
        return {"success": False, "error": "refresh_token ausente"}
    result = request_json("POST", "https://api.mercadolibre.com/oauth/token", {"Content-Type": "application/json"}, {"grant_type": "refresh_token", "client_id": ML_CLIENT_ID, "client_secret": ML_CLIENT_SECRET, "refresh_token": refresh}, 12)
    if result.get("success"):
        await save_token(result.get("data") or {})
    return result

async def ml_request(path, method="GET", payload=None, params=None, retry=True):
    token = await get_token()
    access = token.get("access_token")
    if not access:
        return {"success": False, "error": "Mercado Livre não conectado"}
    query = "?" + urlencode(params) if params else ""
    result = request_json(method, "https://api.mercadolibre.com" + path + query, {"Authorization": f"Bearer {access}", "Content-Type": "application/json"}, payload, 12)
    if result.get("status_code") == 401 and retry:
        refreshed = await refresh_token()
        if refreshed.get("success"):
            return await ml_request(path, method, payload, params, retry=False)
    return result
