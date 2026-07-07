FORBIDDEN_WORDS = [
    "melhor",
    "garantido",
    "100% garantido",
    "original oficial",
    "o mais barato",
]


def clean_text(value):
    return " ".join(str(value or "").strip().split())


def remove_forbidden_words(text):
    cleaned = clean_text(text)
    for word in FORBIDDEN_WORDS:
        cleaned = cleaned.replace(word, "").replace(word.title(), "")
    return clean_text(cleaned)


def generate_title(product, max_length=60):
    brand = clean_text(product.get("brand"))
    name = clean_text(product.get("name"))
    category = clean_text(product.get("category"))

    parts = []
    if brand and brand.lower() not in name.lower():
        parts.append(brand)
    parts.append(name)
    if category and category.lower() not in name.lower():
        parts.append(category)

    title = remove_forbidden_words(" ".join(parts))
    return title[:max_length].strip()


def generate_description(product):
    return "\n".join([
        f"- Produto: {clean_text(product.get('name'))}",
        f"- Marca: {clean_text(product.get('brand')) or 'Não informada'}",
        f"- Categoria: {clean_text(product.get('category')) or 'Não informada'}",
        f"- EAN/GTIN: {clean_text(product.get('ean')) or 'Não informado'}",
        f"- Descrição: {clean_text(product.get('description')) or 'Produto disponível para venda conforme estoque.'}",
        "- Produto novo.",
        "- Antes da publicação final, valide categoria, preço, estoque e atributos obrigatórios.",
        "- Cadastro otimizado pelo CommerceHub AI Listing Optimizer."
    ])


def generate_keywords(product):
    text = f"{product.get('name','')} {product.get('brand','')} {product.get('category','')}".lower()
    stopwords = {"de", "da", "do", "para", "com", "e", "a", "o", "em", "um", "uma"}
    words = []
    for raw in text.replace("-", " ").split():
        word = "".join(ch for ch in raw if ch.isalnum())
        if len(word) > 2 and word not in stopwords and word not in words:
            words.append(word)
    return words[:12]


def suggest_category_search(product):
    name = clean_text(product.get("name")).lower()
    category = clean_text(product.get("category")).lower()

    if "suporte" in name and "celular" in name:
        return "suporte celular carro"
    if "cabo" in name and "usb" in name:
        return "cabo usb c"
    if "microfibra" in name:
        return "pano microfibra limpeza"
    if "tapete" in name and "pet" in category:
        return "tapete higienico pet"
    if "organizador" in name:
        return "organizador cozinha"

    return clean_text(f"{name} {category}")


def seo_score(title, description, keywords):
    checks = {
        "title_length_ok": 20 <= len(title) <= 60,
        "description_present": len(description) >= 120,
        "keywords_present": len(keywords) >= 3,
        "no_forbidden_words": title == remove_forbidden_words(title),
        "not_all_caps": title != title.upper(),
    }
    score = sum(1 for ok in checks.values() if ok)
    return {
        "score": score,
        "max_score": len(checks),
        "percentage": round(score / len(checks) * 100, 2),
        "checks": checks
    }


def optimize_listing(product):
    title = generate_title(product)
    description = generate_description(product)
    keywords = generate_keywords(product)
    category_search = suggest_category_search(product)

    return {
        "title": title,
        "description": description,
        "keywords": keywords,
        "category_search": category_search,
        "seo_score": seo_score(title, description, keywords),
        "warnings": listing_warnings(product)
    }


def listing_warnings(product):
    warnings = []
    if not product.get("ean"):
        warnings.append("EAN/GTIN ausente.")
    if not product.get("brand"):
        warnings.append("Marca ausente.")
    if not product.get("category"):
        warnings.append("Categoria interna ausente.")
    if float(product.get("sale_price") or 0) <= 0:
        warnings.append("Preço de venda ausente.")
    if int(product.get("stock") or 0) <= 0:
        warnings.append("Produto sem estoque.")
    return warnings


def enrich(product):
    return optimize_listing(product)