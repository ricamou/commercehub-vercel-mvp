from pathlib import Path
from datetime import datetime
import json
import uuid


class ProductStoreService:
    def __init__(self):
        self.data_dir = Path("/tmp/commercehub")
        self.data_file = self.data_dir / "products.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _load(self):
        if not self.data_file.exists():
            return []
        try:
            return json.loads(self.data_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self, products):
        self.data_file.write_text(
            json.dumps(products, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def list_products(self):
        return self._load()

    def get_product(self, product_id: str):
        for product in self._load():
            if product.get("id") == product_id:
                return product
        return None

    def create_product(self, payload: dict):
        products = self._load()

        product = {
            "id": str(uuid.uuid4()),
            "sku": payload.get("sku", "").strip(),
            "name": payload.get("name", "").strip(),
            "description": payload.get("description", "").strip(),
            "brand": payload.get("brand", "").strip(),
            "ean": payload.get("ean", "").strip(),
            "internal_category": payload.get("internal_category", "").strip(),
            "ml_category_id": payload.get("ml_category_id", "").strip(),
            "cost_price": float(payload.get("cost_price") or 0),
            "sale_price": float(payload.get("sale_price") or 0),
            "stock": int(payload.get("stock") or 0),
            "weight_kg": float(payload.get("weight_kg") or 0),
            "height_cm": float(payload.get("height_cm") or 0),
            "width_cm": float(payload.get("width_cm") or 0),
            "length_cm": float(payload.get("length_cm") or 0),
            "status": payload.get("status", "draft"),
            "image_url": payload.get("image_url", "").strip(),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        products.append(product)
        self._save(products)
        return product

    def update_product(self, product_id: str, payload: dict):
        products = self._load()

        for index, product in enumerate(products):
            if product.get("id") == product_id:
                updated = {
                    **product,
                    **payload,
                    "updated_at": datetime.utcnow().isoformat()
                }

                numeric_float_fields = [
                    "cost_price", "sale_price", "weight_kg",
                    "height_cm", "width_cm", "length_cm"
                ]
                for field in numeric_float_fields:
                    if field in updated:
                        updated[field] = float(updated[field] or 0)

                if "stock" in updated:
                    updated["stock"] = int(updated["stock"] or 0)

                products[index] = updated
                self._save(products)
                return updated

        return None

    def delete_product(self, product_id: str):
        products = self._load()
        new_products = [p for p in products if p.get("id") != product_id]
        self._save(new_products)
        return len(new_products) != len(products)
