from fastapi import APIRouter
from app.connectors.mercado_livre.client import MercadoLivreClient
from app.services.product_service import ProductService

router = APIRouter()
client = MercadoLivreClient()
product_service = ProductService()


@router.get("/status")
def mercado_livre_status():
    return client.status()


@router.post("/publish-test/{sku}")
def publish_test_product(sku: str):
    product = product_service.get_product_for_marketplace_by_sku(sku)

    if not product:
        return {
            "success": False,
            "message": "Produto não encontrado."
        }

    return client.publish_product(product)
