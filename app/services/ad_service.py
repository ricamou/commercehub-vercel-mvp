class AdService:
    def suggest_search_term(self, product: dict) -> str:
        name = product.get("name", "").lower()
        category = product.get("category", "").lower()

        if "suporte" in name or "veicular" in name or "automotivo" in category:
            return "suporte celular carro"
        if "cabo" in name or "usb" in name:
            return "cabo usb c"
        if "organizador" in name:
            return "organizador cozinha"
        if "microfibra" in name or "pano" in name:
            return "pano microfibra"
        if "pet" in category or "tapete" in name:
            return "tapete higienico pet"

        return product.get("name", "")
