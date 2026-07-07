from engines import calculate_price

MOCK_PRODUCTS = [
    {"sku": "SUP-001", "name": "Suporte Veicular Para Celular", "brand": "MockAuto", "ean": "7890000000011", "category": "Acessórios Automotivos", "description": "Suporte veicular para celular.", "cost_price": 22.90, "stock": 50, "image_url": "https://via.placeholder.com/800"},
    {"sku": "SUP-002", "name": "Cabo USB-C Reforçado 1 Metro", "brand": "MockTech", "ean": "7890000000028", "category": "Acessórios para Celular", "description": "Cabo USB-C reforçado.", "cost_price": 9.90, "stock": 120, "image_url": "https://via.placeholder.com/800"},
    {"sku": "SUP-003", "name": "Organizador Multiuso Para Cozinha", "brand": "MockCasa", "ean": "7890000000035", "category": "Casa e Organização", "description": "Organizador multiuso.", "cost_price": 18.50, "stock": 80, "image_url": "https://via.placeholder.com/800"},
    {"sku": "SUP-004", "name": "Kit 3 Panos de Microfibra", "brand": "MockClean", "ean": "7890000000042", "category": "Casa e Limpeza", "description": "Kit de panos de microfibra.", "cost_price": 12.80, "stock": 200, "image_url": "https://via.placeholder.com/800"},
    {"sku": "SUP-005", "name": "Tapete Higiênico Pet 30 Unidades", "brand": "MockPet", "ean": "7890000000059", "category": "Pet", "description": "Tapete higiênico pet.", "cost_price": 39.90, "stock": 35, "image_url": "https://via.placeholder.com/800"},
]

def mock_products_with_price():
    products = []
    for item in MOCK_PRODUCTS:
        price = calculate_price(item["cost_price"]).get("sale_price", 0)
        products.append({**item, "sale_price": price})
    return products
