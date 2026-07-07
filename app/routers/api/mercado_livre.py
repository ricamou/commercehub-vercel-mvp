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


@router.get("/categories/search")
async def mercado_livre_search_categories(q: str):
    return await client.search_categories(q)


@router.get("/categories/{category_id}/attributes")
async def mercado_livre_category_attributes(category_id: str):
    return await client.get_category_attributes(category_id)


@router.get("/listing-preview/{sku}")
def mercado_livre_listing_preview(sku: str, category_id: str):
    product = product_service.get_product_for_marketplace_by_sku(sku)

    if not product:
        return {
            "success": False,
            "message": "Produto não encontrado."
        }

    return {
        "success": True,
        "payload": client.build_test_listing_payload(product, category_id)
    }


@router.post("/listing-test/{sku}")
async def mercado_livre_publish_test_listing(sku: str, category_id: str):
    product = product_service.get_product_for_marketplace_by_sku(sku)

    if not product:
        return {
            "success": False,
            "message": "Produto não encontrado."
        }

    return await client.publish_test_listing(product, category_id)
