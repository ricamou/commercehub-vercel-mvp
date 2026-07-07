from pathlib import Path
from datetime import datetime
import json, uuid

class Storage:
    def __init__(self):
        self.base = Path("/tmp/commercehub")
        self.base.mkdir(parents=True, exist_ok=True)
        self.products_file = self.base / "products.json"
        self.suppliers_file = self.base / "suppliers.json"
        self.orders_file = self.base / "orders.json"
        self.events_file = self.base / "events.json"

    def _load(self, path):
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self, path, data):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_products(self): return self._load(self.products_file)
    def list_suppliers(self): return self._load(self.suppliers_file)
    def list_orders(self): return self._load(self.orders_file)
    def list_events(self): return self._load(self.events_file)

    def add_product(self, product):
        products = self.list_products()
        product = dict(product)
        product.setdefault("id", str(uuid.uuid4()))
        product.setdefault("created_at", datetime.utcnow().isoformat())
        product["updated_at"] = datetime.utcnow().isoformat()
        products.append(product)
        self._save(self.products_file, products)
        return product

    def add_supplier(self, supplier):
        suppliers = self.list_suppliers()
        supplier = dict(supplier)
        supplier.setdefault("id", str(uuid.uuid4()))
        supplier.setdefault("created_at", datetime.utcnow().isoformat())
        suppliers.append(supplier)
        self._save(self.suppliers_file, suppliers)
        return supplier

    def add_order(self, order):
        orders = self.list_orders()
        order = dict(order)
        order.setdefault("id", str(uuid.uuid4()))
        order.setdefault("created_at", datetime.utcnow().isoformat())
        orders.insert(0, order)
        self._save(self.orders_file, orders[:200])
        return order

    def add_event(self, event_type, message, data=None):
        events = self.list_events()
        event = {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "message": message,
            "data": data or {},
            "created_at": datetime.utcnow().isoformat()
        }
        events.insert(0, event)
        self._save(self.events_file, events[:200])
        return event

storage = Storage()
