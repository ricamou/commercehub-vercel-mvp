from app.services.supplier_service import SupplierService


def test_supplier_returns_products():
    service = SupplierService()
    products = service.list_products()

    assert len(products) > 0
    assert products[0]["sku"].startswith("SUP-")
