from app.core.config import settings


class MercadoLivreClient:
    def status(self):
        has_credentials = bool(settings.ML_CLIENT_ID and settings.ML_CLIENT_SECRET)

        return {
            "connected": False,
            "credentials_configured": has_credentials,
            "message": "Conector Mercado Livre estrutural. OAuth será implementado na v0.3."
        }

    def build_listing_payload(self, product: dict):
        return {
            "title": product["name"][:60],
            "price": product["sale_price"],
            "currency_id": "BRL",
            "available_quantity": product["stock"],
            "buying_mode": "buy_it_now",
            "listing_type_id": "gold_special",
            "condition": "new",
            "seller_custom_field": product["sku"],
            "pictures": [
                {
                    "source": product["image_url"]
                }
            ],
            "attributes": [
                {
                    "id": "BRAND",
                    "value_name": product.get("brand", "Genérico")
                },
                {
                    "id": "GTIN",
                    "value_name": product.get("ean", "")
                }
            ]
        }

    def publish_product(self, product: dict):
        return {
            "success": False,
            "message": "Publicação real será implementada em versão futura.",
            "payload_preview": self.build_listing_payload(product)
        }
