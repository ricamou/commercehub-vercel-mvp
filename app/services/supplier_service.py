from app.connectors.mock_supplier.client import MockSupplierClient


class SupplierService:
    def __init__(self):
        self.client = MockSupplierClient()

    def list_products(self):
        return self.client.list_products()

    def get_product_by_sku(self, sku: str):
        return self.client.get_product_by_sku(sku)
