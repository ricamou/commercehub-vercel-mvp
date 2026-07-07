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
        result = []

        for product in products:
            pricing = self.pricing_service.calculate_sale_price(
                cost_price=product["cost_price"],
                margin_percent=margin_percent
            )

            result.append({
                **product,
                **pricing
            })

        return result

    def get_product_pricing(self, sku: str, margin_percent: float | None = None):
        product = self.supplier_service.get_product_by_sku(sku)

        if not product:
            return None

        pricing = self.pricing_service.calculate_sale_price(
            cost_price=product["cost_price"],
            margin_percent=margin_percent
        )

        return {
            "sku": product["sku"],
            "name": product["name"],
            **pricing
        }

    def get_product_for_marketplace_by_sku(self, sku: str):
        products = self.list_products_with_sale_price()
        for product in products:
            if product["sku"] == sku:
                return product
        return None

    def preview_products_for_marketplace(self, margin_percent: float | None = None):
        products = self.list_products_with_sale_price(margin_percent=margin_percent)
        preview = []

        for product in products:
            preview.append(self.ml_client.build_listing_payload(product))

        return preview
