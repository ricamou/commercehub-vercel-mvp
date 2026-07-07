from urllib.parse import urlencode
import httpx

from app.core.config import settings


class MercadoLivreClient:
    AUTH_URL = "https://auth.mercadolivre.com.br/authorization"
    TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
    API_BASE_URL = "https://api.mercadolibre.com"

    def status(self):
        has_credentials = bool(settings.ML_CLIENT_ID and settings.ML_CLIENT_SECRET and settings.ML_REDIRECT_URI)
        has_access_token = bool(settings.ML_ACCESS_TOKEN)
        has_refresh_token = bool(settings.ML_REFRESH_TOKEN)

        return {
            "connected": has_access_token,
            "credentials_configured": has_credentials,
            "client_id_configured": bool(settings.ML_CLIENT_ID),
            "client_secret_configured": bool(settings.ML_CLIENT_SECRET),
            "redirect_uri_configured": bool(settings.ML_REDIRECT_URI),
            "access_token_configured": has_access_token,
            "refresh_token_configured": has_refresh_token,
            "oauth_ready": has_credentials,
            "redirect_uri": settings.ML_REDIRECT_URI,
            "user_id": settings.ML_USER_ID or None,
            "message": self._status_message(has_credentials, has_access_token)
        }

    def _status_message(self, has_credentials: bool, has_access_token: bool):
        if not has_credentials:
            return "Configure ML_CLIENT_ID, ML_CLIENT_SECRET e ML_REDIRECT_URI na Vercel."
        if not has_access_token:
            return "Credenciais configuradas. Clique em Conectar ao Mercado Livre."
        return "Mercado Livre conectado por token de ambiente."

    def get_authorization_url(self):
        if not settings.ML_CLIENT_ID or not settings.ML_REDIRECT_URI:
            return None

        params = {
            "response_type": "code",
            "client_id": settings.ML_CLIENT_ID,
            "redirect_uri": settings.ML_REDIRECT_URI
        }

        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str):
        payload = {
            "grant_type": "authorization_code",
            "client_id": settings.ML_CLIENT_ID,
            "client_secret": settings.ML_CLIENT_SECRET,
            "code": code,
            "redirect_uri": settings.ML_REDIRECT_URI
        }

        headers = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded"
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(self.TOKEN_URL, data=payload, headers=headers)
            return {
                "status_code": response.status_code,
                "success": response.status_code < 400,
                "data": response.json() if response.content else {}
            }

    async def refresh_access_token(self):
        if not settings.ML_REFRESH_TOKEN:
            return {
                "success": False,
                "message": "ML_REFRESH_TOKEN não configurado."
            }

        payload = {
            "grant_type": "refresh_token",
            "client_id": settings.ML_CLIENT_ID,
            "client_secret": settings.ML_CLIENT_SECRET,
            "refresh_token": settings.ML_REFRESH_TOKEN
        }

        headers = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded"
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(self.TOKEN_URL, data=payload, headers=headers)
            return {
                "status_code": response.status_code,
                "success": response.status_code < 400,
                "data": response.json() if response.content else {}
            }

    async def get_me(self):
        if not settings.ML_ACCESS_TOKEN:
            return {
                "success": False,
                "message": "ML_ACCESS_TOKEN não configurado."
            }

        headers = {
            "Authorization": f"Bearer {settings.ML_ACCESS_TOKEN}"
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self.API_BASE_URL}/users/me", headers=headers)
            return {
                "status_code": response.status_code,
                "success": response.status_code < 400,
                "data": response.json() if response.content else {}
            }

    def build_listing_payload(self, product: dict):
        return {
            "title": product["name"][:60],
            "price": product["sale_price"],
            "currency_id": "BRL",
            "available_quantity": product["stock"],
            "buying_mode": "buy_it_now",
            "listing_type_id": "gold_special",
            "condition": "new",
            "seller_custom_field": product["sku"],
            "pictures": [{"source": product["image_url"]}],
            "attributes": [
                {"id": "BRAND", "value_name": product.get("brand", "Genérico")},
                {"id": "GTIN", "value_name": product.get("ean", "")}
            ]
        }

    def publish_product(self, product: dict):
        return {
            "success": False,
            "message": "Publicação real será implementada na próxima milestone.",
            "payload_preview": self.build_listing_payload(product)
        }
