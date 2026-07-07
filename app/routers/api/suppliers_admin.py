from fastapi import APIRouter, HTTPException

from app.services.supplier_store_service import SupplierStoreService
from app.services.importer_service import ImporterService

router = APIRouter()
supplier_service = SupplierStoreService()
importer_service = ImporterService()


@router.get("/")
def list_suppliers():
    return {
        "success": True,
        "suppliers": supplier_service.list_suppliers()
    }


@router.post("/")
def create_supplier(payload: dict):
    supplier = supplier_service.create_supplier(payload)
    return {
        "success": True,
        "supplier": supplier
    }


@router.get("/{supplier_id}")
def get_supplier(supplier_id: str):
    supplier = supplier_service.get_supplier(supplier_id)

    if not supplier:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado")

    return {
        "success": True,
        "supplier": supplier
    }


@router.put("/{supplier_id}")
def update_supplier(supplier_id: str, payload: dict):
    supplier = supplier_service.update_supplier(supplier_id, payload)

    if not supplier:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado")

    return {
        "success": True,
        "supplier": supplier
    }


@router.delete("/{supplier_id}")
def delete_supplier(supplier_id: str):
    deleted = supplier_service.delete_supplier(supplier_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado")

    return {
        "success": True,
        "deleted": True
    }


@router.get("/mock/preview-import")
def preview_mock_import():
    return importer_service.preview_mock_supplier_import()


@router.post("/mock/import")
def import_mock_supplier():
    return importer_service.import_from_mock_supplier()
