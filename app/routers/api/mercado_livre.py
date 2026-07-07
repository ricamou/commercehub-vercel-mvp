from fastapi import APIRouter

from app.connectors.mercado_livre.client import MercadoLivreClient
from app.services.product_service import ProductService
from app.services.token_service import TokenService

router = APIRouter()
client = MercadoLivreClient()
product_service = ProductService()
token_service = TokenService()


@router.get("/status")
def mercado_livre_status():
    return client.status()


@router.get("/auth-url")
def mercado_livre_auth_url():
    url = client.get_authorization_url()
    return {
        "success": bool(url),
        "auth_url": url,
        "message": "URL gerada com sucesso." if url else "Configure ML_CLIENT_ID e ML_REDIRECT_URI."
    }


@router.get("/token-status")
def mercado_livre_token_status():
    return token_service.get_token_status()


@router.post("/refresh-token")
async def mercado_livre_refresh_token():
    return await client.refresh_access_token()


@router.get("/me")
async def mercado_livre_me():
    return await client.get_me()


@router.post("/publish-test/{sku}")
def publish_test_product(sku: str):
    product = product_service.get_product_for_marketplace_by_sku(sku)
    if not product:
        return {"success": False, "message": "Produto não encontrado."}
    return client.publish_product(product)
