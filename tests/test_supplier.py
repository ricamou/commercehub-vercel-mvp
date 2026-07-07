from app.services.supplier_service import SupplierService


def test_supplier_returns_products():
    products = SupplierService().list_products()
    assert len(products) > 0
