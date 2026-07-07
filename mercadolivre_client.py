from urllib.parse import urlencode
import httpx
from config import settings

class MercadoLivreClient:
    AUTH_URL = "https://auth.mercadolivre.com.br/authorization"
    TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
    API_URL = "https://api.mercadolibre.com"

    def status(self):
        return {
            "credentials_configured": bool(settings.ML_CLIENT_ID and settings.ML_CLIENT_SECRET and settings.ML_REDIRECT_URI),
            "connected": bool(settings.ML_ACCESS_TOKEN),
            "client_id": bool(settings.ML_CLIENT_ID),
            "client_secret": bool(settings.ML_CLIENT_SECRET),
            "redirect_uri": settings.ML_REDIRECT_URI,
            "user_id": settings.ML_USER_ID or None,
        }

    def authorization_url(self):
        if not settings.ML_CLIENT_ID or not settings.ML_REDIRECT_URI:
            return None
        params = {"response_type": "code", "client_id": settings.ML_CLIENT_ID, "redirect_uri": settings.ML_REDIRECT_URI}
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code):
        payload = {
            "grant_type": "authorization_code",
            "client_id": settings.ML_CLIENT_ID,
            "client_secret": settings.ML_CLIENT_SECRET,
            "code": code,
            "redirect_uri": settings.ML_REDIRECT_URI,
        }
        headers = {"accept": "application/json", "content-type": "application/x-www-form-urlencoded"}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(self.TOKEN_URL, data=payload, headers=headers)
            return {"status_code": r.status_code, "success": r.status_code < 400, "data": r.json() if r.content else {}}

    async def me(self):
        if not settings.ML_ACCESS_TOKEN:
            return {"success": False, "message": "ML_ACCESS_TOKEN não configurado."}
        headers = {"Authorization": f"Bearer {settings.ML_ACCESS_TOKEN}"}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{self.API_URL}/users/me", headers=headers)
            return {"status_code": r.status_code, "success": r.status_code < 400, "data": r.json() if r.content else {}}

    async def search_categories(self, q):
        headers = {"Authorization": f"Bearer {settings.ML_ACCESS_TOKEN}"} if settings.ML_ACCESS_TOKEN else {}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{self.API_URL}/sites/MLB/domain_discovery/search", params={"q": q}, headers=headers)
            return {"status_code": r.status_code, "success": r.status_code < 400, "data": r.json() if r.content else []}

    async def publish(self, payload):
        if not settings.ML_ACCESS_TOKEN:
            return {"success": False, "message": "ML_ACCESS_TOKEN não configurado."}
        headers = {"Authorization": f"Bearer {settings.ML_ACCESS_TOKEN}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{self.API_URL}/items", json=payload, headers=headers)
            return {"status_code": r.status_code, "success": r.status_code < 400, "data": r.json() if r.content else {}, "payload_sent": payload}

ml_client = MercadoLivreClient()
