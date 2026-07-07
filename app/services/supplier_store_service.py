from pathlib import Path
from datetime import datetime
import json
import uuid


class SupplierStoreService:
    def __init__(self):
        self.data_dir = Path("/tmp/commercehub")
        self.data_file = self.data_dir / "suppliers.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _load(self):
        if not self.data_file.exists():
            return []
        try:
            return json.loads(self.data_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self, suppliers):
        self.data_file.write_text(
            json.dumps(suppliers, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def list_suppliers(self):
        return self._load()

    def get_supplier(self, supplier_id: str):
        for supplier in self._load():
            if supplier.get("id") == supplier_id:
                return supplier
        return None

    def create_supplier(self, payload: dict):
        suppliers = self._load()

        supplier = {
            "id": str(uuid.uuid4()),
            "name": payload.get("name", "").strip(),
            "document": payload.get("document", "").strip(),
            "type": payload.get("type", "api").strip(),
            "base_url": payload.get("base_url", "").strip(),
            "auth_type": payload.get("auth_type", "none").strip(),
            "status": payload.get("status", "draft").strip(),
            "last_sync_at": None,
            "notes": payload.get("notes", "").strip(),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        suppliers.append(supplier)
        self._save(suppliers)
        return supplier

    def update_supplier(self, supplier_id: str, payload: dict):
        suppliers = self._load()

        for index, supplier in enumerate(suppliers):
            if supplier.get("id") == supplier_id:
                updated = {
                    **supplier,
                    **payload,
                    "updated_at": datetime.utcnow().isoformat()
                }
                suppliers[index] = updated
                self._save(suppliers)
                return updated

        return None

    def delete_supplier(self, supplier_id: str):
        suppliers = self._load()
        new_suppliers = [s for s in suppliers if s.get("id") != supplier_id]
        self._save(new_suppliers)
        return len(new_suppliers) != len(suppliers)
