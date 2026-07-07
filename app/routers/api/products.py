from fastapi import APIRouter, HTTPException, Query
from app.services.product_service import ProductService

router = APIRouter()
service = ProductService()


@router.get("/")
def list_products(margin_percent: float | None = Query(default=None)):
    return service.list_products_with_sale_price(margin_percent=margin_percent)


@router.get("/preview-ml")
def preview_products_for_mercado_livre(margin_percent: float | None = Query(default=None)):
    return service.preview_products_for_marketplace(margin_percent=margin_percent)


@router.get("/pricing/{sku}")
def get_product_pricing(sku: str, margin_percent: float | None = Query(default=None)):
    result = service.get_product_pricing(sku=sku, margin_percent=margin_percent)
    if not result:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return result
