from fastapi import APIRouter, HTTPException

from app.services.product_store_service import ProductStoreService

router = APIRouter()
service = ProductStoreService()


@router.get("/")
def list_catalog_products():
    return {
        "success": True,
        "products": service.list_products()
    }


@router.post("/")
def create_catalog_product(payload: dict):
    product = service.create_product(payload)
    return {
        "success": True,
        "product": product
    }


@router.get("/{product_id}")
def get_catalog_product(product_id: str):
    product = service.get_product(product_id)

    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    return {
        "success": True,
        "product": product
    }


@router.put("/{product_id}")
def update_catalog_product(product_id: str, payload: dict):
    product = service.update_product(product_id, payload)

    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    return {
        "success": True,
        "product": product
    }


@router.delete("/{product_id}")
def delete_catalog_product(product_id: str):
    deleted = service.delete_product(product_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    return {
        "success": True,
        "deleted": True
    }
