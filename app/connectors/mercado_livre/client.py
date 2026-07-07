from urllib.parse import urlencode
import ast
import re
import httpx

from app.core.config import settings


class MercadoLivreClient:
    AUTH_URL = "https://auth.mercadolivre.com.br/authorization"
    TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
    API_BASE_URL = "https://api.mercadolibre.com"

    def _clean_text(self, value) -> str:
        if value is None:
            return ""
        value = str(value).strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1].strip()
        return value.rstrip(",").strip()

    def _parse_dict_if_needed(self, value):
        value = self._clean_text(value)
        if not value:
            return None

        if value.startswith("{") and value.endswith("}"):
            try:
                return ast.literal_eval(value)
            except Exception:
                return None

        return None

    def _extract_field(self, value, field_name: str) -> str:
        value = self._clean_text(value)
        if not value:
            return ""

        parsed = self._parse_dict_if_needed(value)
        if isinstance(parsed, dict) and field_name in parsed:
            return self._clean_text(parsed.get(field_name))

        # Aceita formatos copiados como:
        # 'access_token': 'APP_USR-...'
        # "access_token": "APP_USR-..."
        # access_token=APP_USR-...
        patterns = [
            rf"['\"]{re.escape(field_name)}['\"]\s*:\s*['\"]([^'\"]+)['\"]",
            rf"{re.escape(field_name)}\s*=\s*([^,\s}}]+)",
            rf"{re.escape(field_name)}\s*:\s*([^,\s}}]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, value)
            if match:
                return self._clean_text(match.group(1))

        return value

    def _access_token(self) -> str:
        return self._extract_field(settings.ML_ACCESS_TOKEN, "access_token")

    def _refresh_token(self) -> str:
        return self._extract_field(settings.ML_REFRESH_TOKEN, "refresh_token")

    def _user_id(self) -> str:
        user_id = self._extract_field(settings.ML_USER_ID, "user_id")

        # Se o usuário colou o JSON completo em ML_USER_ID, extrai o user_id.
        parsed = self._parse_dict_if_needed(settings.ML_USER_ID)
        if isinstance(parsed, dict) and "user_id" in parsed:
            return self._clean_text(parsed.get("user_id"))

        return user_id

    def _is_ascii(self, value: str) -> bool:
        try:
            value.encode("ascii")
            return True
        except UnicodeEncodeError:
            return False

    def _is_token_format_valid(self, token: str) -> bool:
        token = self._clean_text(token)
        if not token:
            return False

        if not self._is_ascii(token):
            return False

        invalid_fragments = [
            "{", "}", "access_token", "refresh_token",
            "Token recebido", "Mensagem", "Sucesso", "Dados retornados"
        ]
        return not any(fragment in token for fragment in invalid_fragments)

    def status(self):
        access_token = self._access_token()
        refresh_token = self._refresh_token()
        user_id = self._user_id()

        has_credentials = bool(settings.ML_CLIENT_ID and settings.ML_CLIENT_SECRET and settings.ML_REDIRECT_URI)
        has_access_token = bool(access_token)
        has_refresh_token = bool(refresh_token)

        return {
            "connected": has_access_token and self._is_token_format_valid(access_token),
            "credentials_configured": has_credentials,
            "client_id_configured": bool(settings.ML_CLIENT_ID),
            "client_secret_configured": bool(settings.ML_CLIENT_SECRET),
            "redirect_uri_configured": bool(settings.ML_REDIRECT_URI),
            "access_token_configured": has_access_token,
            "refresh_token_configured": has_refresh_token,
            "access_token_format_valid": self._is_token_format_valid(access_token) if has_access_token else False,
            "refresh_token_format_valid": self._is_token_format_valid(refresh_token) if has_refresh_token else False,
            "oauth_ready": has_credentials,
            "redirect_uri": settings.ML_REDIRECT_URI,
            "user_id": user_id or None,
            "message": self._status_message(has_credentials, access_token)
        }

    def _status_message(self, has_credentials: bool, access_token: str):
        if not has_credentials:
            return "Configure ML_CLIENT_ID, ML_CLIENT_SECRET e ML_REDIRECT_URI na Vercel."
        if not access_token:
            return "Credenciais configuradas. Clique em Conectar ao Mercado Livre."
        if not self._is_token_format_valid(access_token):
            return "Access Token configurado, mas com formato inválido. Copie somente o valor do access_token."
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

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(self.TOKEN_URL, data=payload, headers=headers)
                return {
                    "status_code": response.status_code,
                    "success": response.status_code < 400,
                    "data": response.json() if response.content else {}
                }
        except Exception as exc:
            return {
                "status_code": 500,
                "success": False,
                "data": {"error": "token_exchange_failed", "message": str(exc)}
            }

    async def refresh_access_token(self):
        refresh_token = self._refresh_token()

        if not refresh_token:
            return {"success": False, "message": "ML_REFRESH_TOKEN não configurado."}

        if not self._is_token_format_valid(refresh_token):
            return {
                "success": False,
                "message": "ML_REFRESH_TOKEN com formato inválido. Copie somente o valor do refresh_token."
            }

        payload = {
            "grant_type": "refresh_token",
            "client_id": settings.ML_CLIENT_ID,
            "client_secret": settings.ML_CLIENT_SECRET,
            "refresh_token": refresh_token
        }

        headers = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded"
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(self.TOKEN_URL, data=payload, headers=headers)
                return {
                    "status_code": response.status_code,
                    "success": response.status_code < 400,
                    "data": response.json() if response.content else {}
                }
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    async def get_me(self):
        access_token = self._access_token()

        if not access_token:
            return {"success": False, "message": "ML_ACCESS_TOKEN não configurado.", "data": {}}

        if not self._is_token_format_valid(access_token):
            return {
                "status_code": 400,
                "success": False,
                "message": "ML_ACCESS_TOKEN com formato inválido. Copie somente o valor do access_token.",
                "data": {
                    "hint": "O token deve ser apenas o valor, normalmente começando com APP_USR-, sem JSON inteiro."
                }
            }

        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(f"{self.API_BASE_URL}/users/me", headers=headers)
                try:
                    data = response.json() if response.content else {}
                except Exception:
                    data = {"raw_response": response.text}

                return {
                    "status_code": response.status_code,
                    "success": response.status_code < 400,
                    "data": data
                }
        except Exception as exc:
            return {
                "status_code": 500,
                "success": False,
                "message": "Erro ao consultar /users/me.",
                "data": {"error": str(exc)}
            }


    async def search_categories(self, query: str):
        access_token = self._access_token()
        if not access_token or not self._is_token_format_valid(access_token):
            return {
                "success": False,
                "message": "Access Token inválido ou não configurado.",
                "data": []
            }

        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"q": query}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.API_BASE_URL}/sites/MLB/domain_discovery/search",
                    headers=headers,
                    params=params
                )
                return {
                    "status_code": response.status_code,
                    "success": response.status_code < 400,
                    "data": response.json() if response.content else []
                }
        except Exception as exc:
            return {
                "status_code": 500,
                "success": False,
                "message": "Erro ao buscar categorias.",
                "data": {"error": str(exc)}
            }

    async def get_category_attributes(self, category_id: str):
        access_token = self._access_token()
        if not access_token or not self._is_token_format_valid(access_token):
            return {
                "success": False,
                "message": "Access Token inválido ou não configurado.",
                "data": []
            }

        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.API_BASE_URL}/categories/{category_id}/attributes",
                    headers=headers
                )
                return {
                    "status_code": response.status_code,
                    "success": response.status_code < 400,
                    "data": response.json() if response.content else []
                }
        except Exception as exc:
            return {
                "status_code": 500,
                "success": False,
                "message": "Erro ao buscar atributos da categoria.",
                "data": {"error": str(exc)}
            }

    def get_required_attributes_from_response(self, attributes_response: dict):
        data = attributes_response.get("data", []) if isinstance(attributes_response, dict) else []
        required = []

        for attr in data:
            tags = attr.get("tags", {}) if isinstance(attr, dict) else {}
            if tags.get("required"):
                required.append({
                    "id": attr.get("id"),
                    "name": attr.get("name"),
                    "value_type": attr.get("value_type"),
                    "allowed_units": attr.get("allowed_units", []),
                    "values": attr.get("values", [])[:10] if attr.get("values") else []
                })

        return required

    def build_test_listing_payload(self, product: dict, category_id: str):
        payload = self.build_listing_payload(product)
        payload["category_id"] = category_id
        payload["title"] = f"TESTE - {payload['title']}"[:60]
        return payload

    async def publish_test_listing(self, product: dict, category_id: str):
        access_token = self._access_token()

        if not access_token or not self._is_token_format_valid(access_token):
            return {
                "success": False,
                "message": "Access Token inválido ou não configurado.",
                "data": {}
            }

        payload = self.build_test_listing_payload(product, category_id)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.API_BASE_URL}/items",
                    headers=headers,
                    json=payload
                )
                return {
                    "status_code": response.status_code,
                    "success": response.status_code < 400,
                    "payload_sent": payload,
                    "data": response.json() if response.content else {}
                }
        except Exception as exc:
            return {
                "status_code": 500,
                "success": False,
                "message": "Erro ao publicar anúncio teste.",
                "payload_sent": payload,
                "data": {"error": str(exc)}
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
