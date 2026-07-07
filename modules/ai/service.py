def enrich(product):
    title = f"{product.get('brand','')} {product.get('name','')} {product.get('category','')}".strip()[:60]
    description = "\n".join([
        f"- Produto: {product.get('name')}",
        f"- Marca: {product.get('brand')}",
        f"- Categoria: {product.get('category')}",
        f"- EAN/GTIN: {product.get('ean')}",
        "- Produto novo e pronto para venda conforme disponibilidade de estoque."
    ])
    return {
        "title": title,
        "description": description,
        "category_search": product.get("name", ""),
        "keywords": [w for w in product.get("name", "").lower().split() if len(w) > 2][:10],
        "seo_score": 100 if len(title) >= 20 else 70
    }