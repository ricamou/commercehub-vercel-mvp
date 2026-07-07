from app.connectors.mercado_livre.client import MercadoLivreClient
from app.services.product_service import ProductService
from app.services.supplier_service import SupplierService


class DashboardService:
    def __init__(self):
        self.product_service = ProductService()
        self.supplier_service = SupplierService()
        self.ml_client = MercadoLivreClient()

    def get_dashboard_data(self):
        supplier_products = self.supplier_service.list_products()
        priced_products = self.product_service.list_products_with_sale_price()
        ml_status = self.ml_client.status()

        return {
            "version": "Milestone 1",
            "supplier_products_count": len(supplier_products),
            "priced_products_count": len(priced_products),
            "total_stock": sum(product["stock"] for product in supplier_products),
            "total_cost": round(sum(product["cost_price"] * product["stock"] for product in supplier_products), 2),
            "mercado_livre_connected": ml_status["connected"],
            "mercado_livre_credentials_configured": ml_status["credentials_configured"],
            "flow": "Fornecedor Simulado → CommerceHub → Mercado Livre"
        }
