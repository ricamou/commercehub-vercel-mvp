from app.connectors.mercado_livre.client import MercadoLivreClient
from app.services.pricing_service import PricingService
from app.services.supplier_service import SupplierService


class ProductService:
    def __init__(self):
        self.supplier_service = SupplierService()
        self.pricing_service = PricingService()
        self.ml_client = MercadoLivreClient()

    def list_products_with_sale_price(self, margin_percent: float | None = None):
        products = self.supplier_service.list_products()
        return [{**product, **self.pricing_service.calculate_sale_price(product["cost_price"], margin_percent)} for product in products]

    def get_product_pricing(self, sku: str, margin_percent: float | None = None):
        product = self.supplier_service.get_product_by_sku(sku)
        if not product:
            return None
        return {"sku": product["sku"], "name": product["name"], **self.pricing_service.calculate_sale_price(product["cost_price"], margin_percent)}

    def get_product_for_marketplace_by_sku(self, sku: str):
        for product in self.list_products_with_sale_price():
            if product["sku"] == sku:
                return product
        return None

    def preview_products_for_marketplace(self, margin_percent: float | None = None):
        return [self.ml_client.build_listing_payload(product) for product in self.list_products_with_sale_price(margin_percent)]
