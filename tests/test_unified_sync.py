import asyncio
from copy import deepcopy

from api import index


class FakeStore:
    def __init__(self):
        self.tables = {
            "products": [{
                "id": "p1", "sku": "SKU-1", "name": "Produto Mestre",
                "seo_name": "Produto Mestre SEO", "description": "Descrição oficial",
                "short_description": "Resumo", "ml_category_id": "MLB123",
                "sale_price": 199.90, "ean": "7891234567890", "brand": "Marca X",
                "primary_image_url": "https://cdn.example.com/main.jpg", "sync_status": "pending",
            }],
            "inventory": [{"product_id": "p1", "available": 17}],
            "product_images": [
                {"product_id": "p1", "url": "https://cdn.example.com/main.jpg", "position": 0},
                {"product_id": "p1", "url": "https://cdn.example.com/extra.jpg", "position": 1},
            ],
            "product_attributes": [{"product_id": "p1", "name": "Cor", "value": "Preto"}],
            "product_marketplace_attributes": [{
                "product_id": "p1", "marketplace": "mercado_livre",
                "attribute_id": "COLOR", "value_id": None, "value_name": "Preto",
            }],
            "listings": [{
                "id": "l1", "product_id": "p1", "marketplace": "mercado_livre",
                "title": "Título antigo e incorreto", "description": "Descrição antiga",
                "category_id": "MLB999", "price": 1.0, "available_quantity": 1,
                "status": "draft", "payload": {},
            }],
            "listing_history": [],
        }

    async def select(self, table, query="select=*"):
        rows = deepcopy(self.tables.get(table, []))
        for part in query.split("&"):
            if "=eq." in part:
                key, value = part.split("=eq.", 1)
                rows = [r for r in rows if str(r.get(key)) == value]
        return {"success": True, "data": rows}

    async def update(self, table, query, payload):
        updated = []
        for row in self.tables.get(table, []):
            match = True
            for part in query.split("&"):
                if "=eq." in part:
                    key, value = part.split("=eq.", 1)
                    if str(row.get(key)) != value:
                        match = False
            if match:
                row.update(deepcopy(payload))
                updated.append(deepcopy(row))
        return {"success": True, "data": updated}

    async def insert(self, table, payload):
        self.tables.setdefault(table, []).append(deepcopy(payload))
        return {"success": True, "data": deepcopy(payload)}


def test_product_master_is_single_source_of_truth():
    fake = FakeStore()
    original_store = index.store
    original_get_product = index.s18_get_product
    original_get_listing = index.s19_get_listing
    original_get_listing_by_product = index.s19_get_listing_by_product

    async def get_product(product_id):
        return next((deepcopy(x) for x in fake.tables["products"] if x["id"] == product_id), None)

    async def get_listing(listing_id):
        return next((deepcopy(x) for x in fake.tables["listings"] if x["id"] == listing_id), None)

    async def get_listing_by_product(product_id):
        return next((deepcopy(x) for x in fake.tables["listings"] if x["product_id"] == product_id), None)

    try:
        index.store = fake
        index.s18_get_product = get_product
        index.s19_get_listing = get_listing
        index.s19_get_listing_by_product = get_listing_by_product

        result = asyncio.run(index.s19_sync_product_to_listing("p1", source="automated_test"))
        listing = fake.tables["listings"][0]
        product = fake.tables["products"][0]

        assert result["success"] is True
        assert result["status"] == "synchronized"
        assert listing["title"] == "Produto Mestre SEO"
        assert listing["description"] == "Descrição oficial"
        assert listing["category_id"] == "MLB123"
        assert listing["price"] == 199.90
        assert listing["available_quantity"] == 17
        assert listing["validation_status"] == "pending"
        assert listing["payload"]["product_sync"]["ean"] == "7891234567890"
        assert listing["payload"]["product_sync"]["brand"] == "Marca X"
        assert listing["payload"]["product_sync"]["pictures_count"] == 2
        assert listing["payload"]["product_sync"]["attributes"]["Cor"] == "Preto"
        assert product["sync_status"] == "synchronized"
        assert len(fake.tables["listing_history"]) == 1

        # Idempotência: executar novamente mantém os mesmos dados sem duplicar Listing.
        result2 = asyncio.run(index.s19_sync_product_to_listing("p1", source="automated_test_repeat"))
        assert result2["success"] is True
        assert len(fake.tables["listings"]) == 1
        assert fake.tables["listings"][0]["price"] == 199.90
    finally:
        index.store = original_store
        index.s18_get_product = original_get_product
        index.s19_get_listing = original_get_listing
        index.s19_get_listing_by_product = original_get_listing_by_product


def test_ml_payload_reads_business_fields_from_product_master():
    context = {
        "product": {
            "sku": "SKU-1", "name": "Nome Mestre", "seo_name": "Nome SEO",
            "ml_category_id": "MLB123", "sale_price": 250.0,
            "ean": "7891234567890", "brand": "Marca X",
        },
        "inventory": {"available": 9},
        "images": ["https://cdn.example.com/1.jpg"],
        "attributes": [],
    }
    listing = {
        "title": "Título divergente", "category_id": "MLB999", "price": 1,
        "available_quantity": 1, "currency_id": "BRL", "buying_mode": "buy_it_now",
        "condition": "new", "listing_type_id": "gold_special",
    }
    payload = index.s19_build_ml_payload(context, listing, mode="classic")
    assert payload["title"] == "Nome SEO"
    assert payload["category_id"] == "MLB123"
    assert payload["price"] == 250.0
    assert payload["available_quantity"] == 9
