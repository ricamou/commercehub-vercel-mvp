from datetime import datetime

from app.services.product_store_service import ProductStoreService
from app.connectors.mock_supplier.client import MockSupplierClient


class ImporterService:
    def __init__(self):
        self.product_store = ProductStoreService()
        self.mock_supplier = MockSupplierClient()

    def import_from_mock_supplier(self):
        supplier_products = self.mock_supplier.list_products()
        imported = []
        skipped = []

        existing_products = self.product_store.list_products()
        existing_skus = {product.get("sku") for product in existing_products}

        for product in supplier_products:
            sku = product.get("sku")

            if sku in existing_skus:
                skipped.append({
                    "sku": sku,
                    "reason": "Produto já existe no catálogo."
                })
                continue

            catalog_product = self.product_store.create_product({
                "sku": product.get("sku"),
                "name": product.get("name"),
                "description": product.get("description"),
                "brand": product.get("brand"),
                "ean": product.get("ean"),
                "internal_category": product.get("category"),
                "ml_category_id": "",
                "cost_price": product.get("cost_price"),
                "sale_price": 0,
                "stock": product.get("stock"),
                "weight_kg": product.get("weight_kg"),
                "height_cm": product.get("height_cm"),
                "width_cm": product.get("width_cm"),
                "length_cm": product.get("length_cm"),
                "image_url": product.get("image_url"),
                "status": "imported"
            })

            imported.append(catalog_product)

        return {
            "success": True,
            "source": "mock_supplier",
            "imported_count": len(imported),
            "skipped_count": len(skipped),
            "imported": imported,
            "skipped": skipped,
            "synced_at": datetime.utcnow().isoformat()
        }

    def preview_mock_supplier_import(self):
        supplier_products = self.mock_supplier.list_products()
        catalog_products = self.product_store.list_products()
        catalog_skus = {product.get("sku") for product in catalog_products}

        preview = []
        for product in supplier_products:
            preview.append({
                "sku": product.get("sku"),
                "name": product.get("name"),
                "stock": product.get("stock"),
                "cost_price": product.get("cost_price"),
                "already_exists": product.get("sku") in catalog_skus
            })

        return {
            "success": True,
            "source": "mock_supplier",
            "products_count": len(preview),
            "products": preview
        }
