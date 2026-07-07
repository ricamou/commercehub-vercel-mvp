from fastapi import APIRouter, HTTPException
from app.services.supplier_service import SupplierService

router = APIRouter()
service = SupplierService()


@router.get("/products")
def list_supplier_products():
    return service.list_products()


@router.get("/products/{sku}")
def get_supplier_product(sku: str):
    product = service.get_product_by_sku(sku)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return product
