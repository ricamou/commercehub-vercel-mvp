from app.connectors.mock_supplier.data import MOCK_PRODUCTS


class MockSupplierClient:
    def list_products(self):
        return MOCK_PRODUCTS

    def get_product_by_sku(self, sku: str):
        for product in MOCK_PRODUCTS:
            if product["sku"] == sku:
                return product
        return None
