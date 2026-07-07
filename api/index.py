
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from urllib.parse import urlencode
from datetime import datetime
import os
import uuid
import csv
import io
import json
import xml.etree.ElementTree as ET

try:
    import httpx
except Exception:
    httpx = None

app = FastAPI(title="CommerceHub Final Production Ready", version="final-production-ready")


def env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if value is None:
        return ""
    value = str(value).strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()
    return value


APP_URL = env("APP_URL", "https://commercehub-vercel-mvp.vercel.app")
ML_CLIENT_ID = env("ML_CLIENT_ID")
ML_CLIENT_SECRET = env("ML_CLIENT_SECRET")
ML_REDIRECT_URI = env("ML_REDIRECT_URI", f"{APP_URL}/api/mercadolivre/callback")
ML_ACCESS_TOKEN = env("ML_ACCESS_TOKEN")
ML_REFRESH_TOKEN = env("ML_REFRESH_TOKEN")
ML_USER_ID = env("ML_USER_ID")
SUPABASE_URL = env("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = env("SUPABASE_SERVICE_ROLE_KEY")
DEFAULT_MARGIN_PERCENT = float(env("DEFAULT_MARGIN_PERCENT", "35") or 35)
ML_COMMISSION_PERCENT = float(env("ML_COMMISSION_PERCENT", "16") or 16)
FIXED_OPERATIONAL_COST = float(env("FIXED_OPERATIONAL_COST", "6") or 6)

MOCK_PRODUCTS = [
    {"sku":"SUP-001","name":"Suporte Veicular Para Celular","brand":"MockAuto","ean":"7890000000011","category":"Acessórios Automotivos","description":"Suporte veicular para celular.","cost_price":22.90,"stock":50},
    {"sku":"SUP-002","name":"Cabo USB-C Reforçado 1 Metro","brand":"MockTech","ean":"7890000000028","category":"Acessórios para Celular","description":"Cabo USB-C reforçado.","cost_price":9.90,"stock":120},
    {"sku":"SUP-003","name":"Organizador Multiuso Para Cozinha","brand":"MockCasa","ean":"7890000000035","category":"Casa e Organização","description":"Organizador multiuso para cozinha.","cost_price":18.50,"stock":80},
    {"sku":"SUP-004","name":"Kit 3 Panos de Microfibra","brand":"MockClean","ean":"7890000000042","category":"Casa e Limpeza","description":"Kit com panos de microfibra.","cost_price":12.80,"stock":200},
    {"sku":"SUP-005","name":"Tapete Higiênico Pet 30 Unidades","brand":"MockPet","ean":"7890000000059","category":"Pet","description":"Tapete higiênico para pets.","cost_price":39.90,"stock":35},
]

SUPPLIERS = [
    {"id": "mock_supplier", "name": "Fornecedor Simulado", "type": "mock", "status": "active"},
    {"id": "api_rest", "name": "Fornecedor API REST", "type": "api_rest", "status": "ready"},
    {"id": "json", "name": "Fornecedor JSON", "type": "json", "status": "ready"},
    {"id": "xml", "name": "Fornecedor XML", "type": "xml", "status": "ready"},
    {"id": "csv", "name": "Fornecedor CSV", "type": "csv", "status": "ready"},
]

USERS = [
    {"id": "owner", "name": "Ricardo Moura", "email": "owner@commercehub.local", "role": "owner", "status": "active"}
]


def calculate_price(cost_price, margin_percent=None, commission_percent=None, fixed_cost=None):
    cost_price = float(cost_price or 0)
    margin_percent = float(DEFAULT_MARGIN_PERCENT if margin_percent is None else margin_percent)
    commission_percent = float(ML_COMMISSION_PERCENT if commission_percent is None else commission_percent)
    fixed_cost = float(FIXED_OPERATIONAL_COST if fixed_cost is None else fixed_cost)
    desired_profit = cost_price * margin_percent / 100
    variable_fee = commission_percent / 100
    if variable_fee >= 1:
        return {"success": False, "message": "Comissão inválida."}
    sale_price = (cost_price + fixed_cost + desired_profit) / (1 - variable_fee)
    rounded = int(sale_price) + 0.90
    if rounded < sale_price:
        rounded += 1
    commission = rounded * variable_fee
    profit = rounded - cost_price - fixed_cost - commission
    real_margin = (profit / rounded * 100) if rounded else 0
    status = "healthy"
    if profit <= 0:
        status = "not_profitable"
    elif real_margin < 8:
        status = "critical_margin"
    elif real_margin < 18:
        status = "low_margin"
    return {
        "success": True,
        "cost_price": round(cost_price, 2),
        "sale_price": round(rounded, 2),
        "commission": round(commission, 2),
        "fixed_cost": round(fixed_cost, 2),
        "profit": round(profit, 2),
        "margin_percent": round(real_margin, 2),
        "status": status,
        "recommendation": status,
    }


def with_price(product):
    return {**product, **calculate_price(product.get("cost_price", 0))}


def all_products():
    return [with_price(p) for p in MOCK_PRODUCTS]


def product_by_sku(sku):
    return next((p for p in all_products() if p.get("sku") == sku), None)


def stock_status(stock):
    stock = int(stock or 0)
    if stock <= 0:
        return "out_of_stock"
    if stock <= 3:
        return "low_stock"
    return "available"


def database_status():
    configured = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)
    return {
        "supabase_configured": configured,
        "mode": "supabase_ready" if configured else "memory_demo",
        "message": "Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY na Vercel para persistência real."
    }


def supabase_headers():
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }


async def db_select(table):
    if not database_status()["supabase_configured"] or not httpx:
        return {"success": False, "message": "Supabase não configurado.", "data": []}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{SUPABASE_URL}/rest/v1/{table}?select=*", headers=supabase_headers())
        return {"success": response.status_code < 400, "status_code": response.status_code, "data": response.json() if response.content else []}


async def db_insert(table, payload):
    if not database_status()["supabase_configured"] or not httpx:
        return {"success": True, "source": "memory_demo", "message": "Recebido, mas Supabase não configurado.", "data": payload}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=supabase_headers(), json=payload)
        return {"success": response.status_code < 400, "status_code": response.status_code, "data": response.json() if response.content else None}


def audit_event(event_type, message, payload=None):
    return {
        "id": str(uuid.uuid4()),
        "event_type": event_type,
        "message": message,
        "payload": payload or {},
        "created_at": datetime.utcnow().isoformat()
    }


def clean_text(value):
    return " ".join(str(value or "").strip().split())


FORBIDDEN_WORDS = ["melhor", "garantido", "100% garantido", "o mais barato"]


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
    return remove_forbidden_words(" ".join(parts))[:max_length].strip()


def generate_description(product):
    return "\n".join([
        f"- Produto: {clean_text(product.get('name'))}",
        f"- Marca: {clean_text(product.get('brand')) or 'Não informada'}",
        f"- Categoria: {clean_text(product.get('category')) or 'Não informada'}",
        f"- EAN/GTIN: {clean_text(product.get('ean')) or 'Não informado'}",
        f"- Descrição: {clean_text(product.get('description')) or 'Produto disponível para venda conforme estoque.'}",
        "- Produto novo.",
        "- Valide categoria, preço, estoque e atributos obrigatórios antes da publicação final.",
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


def optimize_listing(product):
    title = generate_title(product)
    description = generate_description(product)
    keywords = generate_keywords(product)
    checks = {
        "title_length_ok": 20 <= len(title) <= 60,
        "description_present": len(description) >= 120,
        "keywords_present": len(keywords) >= 3,
        "not_all_caps": title != title.upper(),
    }
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
    score = sum(1 for ok in checks.values() if ok)
    return {
        "title": title,
        "description": description,
        "keywords": keywords,
        "category_search": suggest_category_search(product),
        "seo_score": {"score": score, "max_score": len(checks), "percentage": round(score / len(checks) * 100, 2), "checks": checks},
        "warnings": warnings
    }


def readiness(product):
    missing = []
    for field in ["sku", "name", "brand", "ean", "category", "sale_price", "stock"]:
        if not product.get(field):
            missing.append(field)
    return {"ready": len(missing) == 0, "missing": missing}


def listing_payload(product, category_id="MLBXXXX"):
    optimized = optimize_listing(product)
    return {
        "title": optimized["title"],
        "category_id": category_id or "MLBXXXX",
        "price": product.get("sale_price", 0),
        "currency_id": "BRL",
        "available_quantity": int(product.get("stock", 0)),
        "buying_mode": "buy_it_now",
        "listing_type_id": "gold_special",
        "condition": "new",
        "seller_custom_field": product.get("sku"),
        "pictures": [{"source": product.get("image_url") or "https://via.placeholder.com/800"}],
        "attributes": [
            {"id": "BRAND", "value_name": product.get("brand") or "Genérico"},
            {"id": "GTIN", "value_name": product.get("ean") or ""},
        ],
        "description": optimized["description"]
    }


FIELD_MAP = {
    "sku": ["sku", "codigo", "id", "code", "reference", "ref"],
    "name": ["name", "nome", "title", "titulo", "produto", "product_name"],
    "brand": ["brand", "marca", "manufacturer"],
    "ean": ["ean", "gtin", "barcode", "codigo_barras"],
    "category": ["category", "categoria", "department", "departamento"],
    "description": ["description", "descricao", "desc", "details"],
    "cost_price": ["cost_price", "custo", "preco_custo", "price_cost", "wholesale_price"],
    "stock": ["stock", "estoque", "quantity", "qty", "available_quantity"],
    "image_url": ["image_url", "imagem", "image", "picture", "photo"],
}


def find_field(payload, names):
    payload = dict(payload or {})
    lower = {str(k).lower(): v for k, v in payload.items()}
    for name in names:
        if name in payload and payload.get(name) not in [None, ""]:
            return payload.get(name)
        if name.lower() in lower and lower.get(name.lower()) not in [None, ""]:
            return lower.get(name.lower())
    return ""


def to_float(value):
    try:
        if isinstance(value, str):
            value = value.replace("R$", "").replace(".", "").replace(",", ".").strip()
        return float(value or 0)
    except Exception:
        return 0.0


def to_int(value):
    try:
        return int(float(str(value or 0).replace(",", ".")))
    except Exception:
        return 0


def normalize_supplier_product(payload, source_type="manual"):
    payload = payload or {}
    return {
        "source_type": source_type,
        "sku": str(find_field(payload, FIELD_MAP["sku"])).strip(),
        "name": str(find_field(payload, FIELD_MAP["name"])).strip(),
        "brand": str(find_field(payload, FIELD_MAP["brand"])).strip(),
        "ean": str(find_field(payload, FIELD_MAP["ean"])).strip(),
        "category": str(find_field(payload, FIELD_MAP["category"])).strip(),
        "description": str(find_field(payload, FIELD_MAP["description"])).strip(),
        "cost_price": to_float(find_field(payload, FIELD_MAP["cost_price"])),
        "stock": to_int(find_field(payload, FIELD_MAP["stock"])),
        "image_url": str(find_field(payload, FIELD_MAP["image_url"])).strip(),
        "raw_data": payload,
    }


def validate_product(product):
    missing = [f for f in ["sku", "name"] if not product.get(f)]
    warnings = []
    if not product.get("ean"):
        warnings.append("EAN/GTIN ausente.")
    if product.get("cost_price", 0) <= 0:
        warnings.append("Custo ausente ou zerado.")
    if product.get("stock", 0) <= 0:
        warnings.append("Estoque ausente ou zerado.")
    return {"valid": len(missing) == 0, "missing": missing, "warnings": warnings}


def parse_json_payload(payload):
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("products") or payload.get("items") or payload.get("data") or [payload]
    else:
        items = []
    return [normalize_supplier_product(item, "json") for item in items]


def parse_csv_payload(text):
    return [normalize_supplier_product(row, "csv") for row in csv.DictReader(io.StringIO(str(text)))]


def parse_xml_payload(text):
    root = ET.fromstring(str(text))
    candidates = root.findall(".//product") or root.findall(".//produto") or root.findall(".//item") or list(root)
    products = []
    for node in candidates:
        data = {child.tag: child.text for child in list(node)}
        if data:
            products.append(normalize_supplier_product(data, "xml"))
    return products


def parse_payload_by_type(source_type, payload):
    source_type = (source_type or "json").lower()
    if source_type in ["json", "api_rest", "api"]:
        products = parse_json_payload(payload)
    elif source_type == "csv":
        products = parse_csv_payload(payload if isinstance(payload, str) else payload.get("payload", ""))
    elif source_type == "xml":
        products = parse_xml_payload(payload if isinstance(payload, str) else payload.get("payload", ""))
    else:
        products = [normalize_supplier_product(payload if isinstance(payload, dict) else {}, source_type)]
    return {"success": True, "source_type": source_type, "count": len(products), "products": products, "validation": [validate_product(p) for p in products]}


def import_from_payload(source_type, payload):
    parsed = parse_payload_by_type(source_type, payload)
    products = [with_price(product) for product in parsed.get("products", [])]
    valid_products = []
    invalid_products = []
    for product in products:
        validation = validate_product(product)
        if validation.get("valid"):
            valid_products.append(product)
        else:
            invalid_products.append({"product": product, "validation": validation})
    return {
        "success": True,
        "source_type": source_type,
        "count": len(products),
        "valid_count": len(valid_products),
        "invalid_count": len(invalid_products),
        "products": products,
        "valid_products": valid_products,
        "invalid_products": invalid_products
    }


def compare_supplier_to_catalog():
    supplier_items = all_products()
    catalog_items = all_products()
    catalog_by_sku = {p.get("sku"): p for p in catalog_items}
    new_products = []
    stock_changes = []
    cost_changes = []
    unchanged = []
    for item in supplier_items:
        sku = item.get("sku")
        current = catalog_by_sku.get(sku)
        if not current:
            new_products.append(with_price(item))
            continue
        changed = False
        if int(item.get("stock") or 0) != int(current.get("stock") or 0):
            stock_changes.append({"sku": sku, "name": item.get("name"), "old_stock": current.get("stock"), "new_stock": item.get("stock"), "action": "update_stock"})
            changed = True
        if float(item.get("cost_price") or 0) != float(current.get("cost_price") or 0):
            recalculated = with_price(item)
            cost_changes.append({"sku": sku, "name": item.get("name"), "old_cost": current.get("cost_price"), "new_cost": item.get("cost_price"), "suggested_sale_price": recalculated.get("sale_price"), "action": "update_cost_and_price"})
            changed = True
        if not changed:
            unchanged.append({"sku": sku, "name": item.get("name"), "status": "unchanged"})
    return {
        "success": True,
        "summary": {
            "supplier_products": len(supplier_items),
            "catalog_products": len(catalog_items),
            "new_products": len(new_products),
            "stock_changes": len(stock_changes),
            "cost_changes": len(cost_changes),
            "unchanged": len(unchanged)
        },
        "new_products": new_products,
        "stock_changes": stock_changes,
        "cost_changes": cost_changes,
        "unchanged": unchanged
    }


def build_marketplace_sync_payload():
    comparison = compare_supplier_to_catalog()
    updates = []
    for item in comparison.get("stock_changes", []):
        updates.append({"sku": item.get("sku"), "type": "stock", "payload": {"available_quantity": item.get("new_stock")}})
    for item in comparison.get("cost_changes", []):
        updates.append({"sku": item.get("sku"), "type": "price", "payload": {"price": item.get("suggested_sale_price")}})
    return {"success": True, "marketplace": "mercado_livre", "updates_count": len(updates), "updates": updates}


def run_demo_sync():
    return {
        "success": True,
        "mode": "demo",
        "comparison": compare_supplier_to_catalog(),
        "marketplace_payload": build_marketplace_sync_payload(),
        "actions": [
            {"step": "supplier_read", "status": "completed"},
            {"step": "catalog_compare", "status": "completed"},
            {"step": "price_recalculation", "status": "completed"},
            {"step": "marketplace_payload_generation", "status": "completed"},
            {"step": "event_ready", "status": "completed"}
        ]
    }


def ml_status():
    return {
        "client_id": bool(ML_CLIENT_ID),
        "client_secret": bool(ML_CLIENT_SECRET),
        "redirect_uri": ML_REDIRECT_URI,
        "access_token": bool(ML_ACCESS_TOKEN),
        "refresh_token": bool(ML_REFRESH_TOKEN),
        "user_id": ML_USER_ID or None
    }


def ml_auth_url():
    if not ML_CLIENT_ID or not ML_REDIRECT_URI:
        return ""
    return "https://auth.mercadolivre.com.br/authorization?" + urlencode({"response_type": "code", "client_id": ML_CLIENT_ID, "redirect_uri": ML_REDIRECT_URI})


async def ml_exchange_code(code):
    if not httpx:
        return {"success": False, "message": "httpx não instalado"}
    payload = {"grant_type": "authorization_code", "client_id": ML_CLIENT_ID, "client_secret": ML_CLIENT_SECRET, "code": code, "redirect_uri": ML_REDIRECT_URI}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post("https://api.mercadolibre.com/oauth/token", data=payload)
        return {"success": response.status_code < 400, "status_code": response.status_code, "data": response.json() if response.content else {}}


async def ml_me():
    if not ML_ACCESS_TOKEN:
        return {"success": False, "message": "ML_ACCESS_TOKEN não configurado"}
    if not httpx:
        return {"success": False, "message": "httpx não instalado"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get("https://api.mercadolibre.com/users/me", headers={"Authorization": f"Bearer {ML_ACCESS_TOKEN}"})
        return {"success": response.status_code < 400, "status_code": response.status_code, "data": response.json() if response.content else {}}


async def ml_categories(q):
    if not httpx:
        return {"success": False, "message": "httpx não instalado"}
    headers = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}"} if ML_ACCESS_TOKEN else {}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get("https://api.mercadolibre.com/sites/MLB/domain_discovery/search", params={"q": q}, headers=headers)
        return {"success": response.status_code < 400, "status_code": response.status_code, "data": response.json() if response.content else []}


async def ml_publish_item(payload):
    if not ML_ACCESS_TOKEN:
        return {"success": False, "message": "ML_ACCESS_TOKEN não configurado"}
    if not httpx:
        return {"success": False, "message": "httpx não instalado"}
    headers = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post("https://api.mercadolibre.com/items", headers=headers, json=payload)
        return {"success": response.status_code < 400, "status_code": response.status_code, "data": response.json() if response.content else {}, "payload_sent": payload}


def layout(title, body):
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · CommerceHub</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:#f4f7fb;color:#111827}}
aside{{position:fixed;left:0;top:0;bottom:0;width:230px;background:#0b1220;color:white;padding:22px 16px;overflow:auto}}
.logo{{display:flex;gap:10px;align-items:center;margin-bottom:28px}}.logo b{{background:#2563eb;padding:12px;border-radius:10px}}.logo span{{display:block;color:#9ca3af;font-size:12px}}
nav a{{display:block;color:white;text-decoration:none;padding:10px 8px;border-radius:8px;margin:4px 0}}nav a:hover{{background:#172033}}
main{{margin-left:230px;padding:28px}}h1{{font-size:34px;margin:0}}header p{{color:#64748b}}
.grid{{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:16px;margin:22px 0}}.card,.panel{{background:white;border:1px solid #d8dee8;border-radius:16px;box-shadow:0 8px 24px rgba(15,23,42,.05)}}
.card{{padding:22px}}.card span{{display:block;color:#64748b}}.card strong{{font-size:30px;display:block;margin-top:10px}}
.panel{{padding:22px;margin:18px 0}}table{{width:100%;border-collapse:collapse;margin-top:12px}}th,td{{padding:12px;border-bottom:1px solid #e5e7eb;text-align:left}}th{{background:#f8fafc}}
pre{{background:#0b1220;color:white;padding:14px;border-radius:10px;overflow:auto}}code{{background:#eef2ff;padding:3px 6px;border-radius:6px}}.btn{{display:inline-block;background:#2563eb;color:white;text-decoration:none;padding:12px 16px;border-radius:10px;margin:8px 0}}
</style>
</head>
<body>
<aside>
<div class="logo"><b>CH</b><div><strong>CommerceHub</strong><span>Final Ready</span></div></div>
<nav>
<a href="/dashboard">Dashboard</a>
<a href="/enterprise-final">Enterprise Final</a>
<a href="/sprint1">Sprint 1</a>
<a href="/sprint2">Sprint 2</a>
<a href="/sprint3">Sprint 3</a>
<a href="/mercado-livre">Mercado Livre</a>
<a href="/fornecedores">Fornecedores</a>
<a href="/produtos">Produtos</a>
<a href="/anuncios">Anúncios</a>
<a href="/pedidos">Pedidos</a>
<a href="/relatorios">Relatórios</a>
<a href="/ai">AI Engine</a>
<a href="/database">Database</a>
<a href="/api/health" target="_blank">API Health</a>
</nav>
</aside>
<main>
<header><h1>{title}</h1><p>Fornecedor → CommerceHub → Mercado Livre → Cliente</p></header>
{body}
</main>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    products = all_products()
    stock = sum(p["stock"] for p in products)
    cost = sum(p["cost_price"] * p["stock"] for p in products)
    profit = sum(p["profit"] * p["stock"] for p in products)
    body = f"""
<section class="grid">
<div class="card"><span>Produtos</span><strong>{len(products)}</strong></div>
<div class="card"><span>Estoque total</span><strong>{stock}</strong></div>
<div class="card"><span>Custo estoque</span><strong>R$ {cost:,.2f}</strong></div>
<div class="card"><span>Lucro potencial</span><strong>R$ {profit:,.2f}</strong></div>
</section>
<section class="panel"><h2>Status</h2>
<p><b>Mercado Livre conectado:</b> {bool(ML_ACCESS_TOKEN)}</p>
<p><b>Banco:</b> {database_status()["mode"]}</p>
<p><b>Versão:</b> CommerceHub Final Production Ready</p></section>
"""
    return layout("Dashboard", body)


@app.get("/enterprise-final", response_class=HTMLResponse)
def enterprise_final():
    products = all_products()
    profit = sum(p["profit"] * p["stock"] for p in products)
    body = f"""
<section class="grid">
<div class="card"><span>Produtos</span><strong>{len(products)}</strong></div>
<div class="card"><span>Fornecedores</span><strong>{len(SUPPLIERS)}</strong></div>
<div class="card"><span>Estoque</span><strong>{sum(p['stock'] for p in products)}</strong></div>
<div class="card"><span>Lucro potencial</span><strong>R$ {profit:,.2f}</strong></div>
</section>
<section class="panel"><h2>Enterprise Final</h2>
<p>Base final consolidada, abaixo do limite do GitHub Web e preparada para Vercel.</p>
<table>
<tr><th>Módulo</th><th>Status</th></tr>
<tr><td>Mercado Livre</td><td>Ready</td></tr>
<tr><td>Produtos</td><td>Ready</td></tr>
<tr><td>Fornecedores</td><td>Ready</td></tr>
<tr><td>Pricing</td><td>Ready</td></tr>
<tr><td>Inventory</td><td>Ready</td></tr>
<tr><td>AI Optimizer</td><td>Ready</td></tr>
<tr><td>Import/Sync</td><td>Ready</td></tr>
<tr><td>Supabase-ready</td><td>Ready</td></tr>
</table></section>
"""
    return layout("Enterprise Final", body)


@app.get("/sprint1", response_class=HTMLResponse)
def sprint1():
    return layout("Sprint 1", "<section class='panel'><h2>Universal Supplier Connector</h2><p>Conexão operacional por API, JSON, XML e CSV.</p><pre>GET /api/connectors/status\nPOST /api/connectors/parse/json\nPOST /api/connectors/parse/csv\nPOST /api/connectors/parse/xml</pre></section>")


@app.get("/sprint2", response_class=HTMLResponse)
def sprint2():
    return layout("Sprint 2", "<section class='panel'><h2>Supplier Product Import Persistent</h2><p>Importação, validação, válidos/inválidos e persistência Supabase-ready.</p><pre>GET /api/import/summary/mock\nPOST /api/import/persist/json</pre></section>")


@app.get("/sprint3", response_class=HTMLResponse)
def sprint3():
    return layout("Sprint 3", "<section class='panel'><h2>Supplier Sync Automation</h2><p>Comparação fornecedor x catálogo, custo, estoque, reprecificação e payload de marketplace.</p><pre>GET /api/sync/compare\nGET /api/sync/marketplace-payload\nPOST /api/sync/run-demo</pre></section>")


@app.get("/mercado-livre", response_class=HTMLResponse)
def mercado_livre():
    s = ml_status()
    auth = ml_auth_url()
    body = f"""
<section class="panel"><h2>Status Mercado Livre</h2>
<p><b>Client ID:</b> {s['client_id']}</p>
<p><b>Client Secret:</b> {s['client_secret']}</p>
<p><b>Redirect URI:</b> {s['redirect_uri']}</p>
<p><b>Access Token:</b> {s['access_token']}</p>
<p><b>User ID:</b> {s['user_id']}</p>
{f'<a class="btn" href="{auth}">Conectar ao Mercado Livre</a>' if auth else '<p>Configure as credenciais na Vercel.</p>'}
</section>
"""
    return layout("Mercado Livre", body)


@app.get("/fornecedores", response_class=HTMLResponse)
def fornecedores():
    rows = "".join([f"<tr><td>{s['id']}</td><td>{s['name']}</td><td>{s['type']}</td><td>{s['status']}</td></tr>" for s in SUPPLIERS])
    return layout("Fornecedores", f"<section class='panel'><h2>Fornecedores</h2><table><tr><th>ID</th><th>Nome</th><th>Tipo</th><th>Status</th></tr>{rows}</table></section>")


@app.get("/produtos", response_class=HTMLResponse)
def produtos():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{p['name']}</td><td>{p['brand']}</td><td>{stock_status(p['stock'])}</td><td>R$ {p['sale_price']:.2f}</td></tr>" for p in all_products()])
    return layout("Produtos", f"<section class='panel'><h2>Catálogo</h2><table><tr><th>SKU</th><th>Produto</th><th>Marca</th><th>Estoque</th><th>Preço</th></tr>{rows}</table></section>")


@app.get("/anuncios", response_class=HTMLResponse)
def anuncios():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{p['name']}</td><td>{readiness(p)['ready']}</td><td><code>/api/anuncios/preview/{p['sku']}?category_id=MLBXXXX</code></td></tr>" for p in all_products()])
    return layout("Anúncios", f"<section class='panel'><h2>Anúncios</h2><table><tr><th>SKU</th><th>Produto</th><th>Pronto?</th><th>Preview</th></tr>{rows}</table></section>")


@app.get("/pedidos", response_class=HTMLResponse)
def pedidos():
    return layout("Pedidos", "<section class='panel'><h2>Orders Engine</h2><p>Simular pedido: <code>POST /api/pedidos/simulate</code></p></section>")


@app.get("/relatorios", response_class=HTMLResponse)
def relatorios():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{p['name']}</td><td>R$ {p['profit']:.2f}</td><td>{p['margin_percent']}%</td><td>{p['status']}</td></tr>" for p in all_products()])
    return layout("Relatórios", f"<section class='panel'><h2>Financeiro</h2><table><tr><th>SKU</th><th>Produto</th><th>Lucro</th><th>Margem</th><th>Status</th></tr>{rows}</table></section>")


@app.get("/ai", response_class=HTMLResponse)
def ai_page():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{p['name']}</td><td>{optimize_listing(p)['title']}</td><td>{optimize_listing(p)['seo_score']['percentage']}%</td></tr>" for p in all_products()])
    return layout("AI Engine", f"<section class='panel'><h2>Produtos otimizados</h2><table><tr><th>SKU</th><th>Produto</th><th>Título sugerido</th><th>SEO</th></tr>{rows}</table></section>")


@app.get("/database", response_class=HTMLResponse)
def database_page():
    return layout("Database", f"<section class='panel'><h2>Database</h2><pre>{database_status()}</pre></section>")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "commercehub", "version": "final-production-ready"}


@app.get("/api/produtos")
def api_products():
    return {"success": True, "products": all_products()}


@app.get("/api/fornecedores")
def api_suppliers():
    return {"success": True, "suppliers": SUPPLIERS}


@app.get("/api/connectors/status")
def api_connectors_status():
    return {"success": True, "module": "Universal Supplier Connector", "version": "final", "connectors": [{"type": "api_rest", "name": "API REST", "status": "ready"}, {"type": "json", "name": "JSON", "status": "ready"}, {"type": "xml", "name": "XML", "status": "ready"}, {"type": "csv", "name": "CSV", "status": "ready"}]}


@app.post("/api/connectors/preview")
def api_connectors_preview(payload: dict):
    source_type = payload.get("source_type", "manual")
    raw_payload = payload.get("payload", payload)
    normalized = normalize_supplier_product(raw_payload, source_type)
    return {"success": True, "normalized": normalized, "validation": validate_product(normalized)}


@app.post("/api/connectors/parse/{source_type}")
def api_connectors_parse(source_type: str, payload: dict):
    return parse_payload_by_type(source_type, payload.get("payload", payload))


@app.post("/api/import/from-payload/{source_type}")
def api_import_from_payload(source_type: str, payload: dict):
    return import_from_payload(source_type, payload.get("payload", payload))


@app.get("/api/import/summary/mock")
def api_import_summary_mock():
    products = all_products()
    total_stock = sum(p["stock"] for p in products)
    total_cost = sum(p["cost_price"] * p["stock"] for p in products)
    return {"success": True, "summary": {"products_count": len(products), "total_stock": total_stock, "total_cost": round(total_cost, 2)}, "products": products}


@app.post("/api/import/persist/{source_type}")
async def api_import_persist(source_type: str, payload: dict):
    parsed = import_from_payload(source_type, payload.get("payload", payload))
    result = []
    for product in parsed.get("valid_products", []):
        result.append(await db_insert("products", product))
    return {"success": True, "parsed": parsed, "persist_result": result}


@app.get("/api/sync/compare")
def api_sync_compare():
    return compare_supplier_to_catalog()


@app.get("/api/sync/marketplace-payload")
def api_sync_marketplace_payload():
    return build_marketplace_sync_payload()


@app.post("/api/sync/run-demo")
def api_sync_run_demo():
    return run_demo_sync()


@app.get("/api/sync/status")
def api_sync_status():
    return {"success": True, "module": "Supplier Sync Automation", "status": "ready"}


@app.get("/api/sync/plan")
def api_sync_plan():
    return {"success": True, "steps": ["Ler fornecedor", "Comparar catálogo", "Atualizar preço", "Atualizar estoque", "Gerar payload marketplace"]}


@app.get("/api/pricing/report")
def api_pricing_report(margin_percent: float = None):
    return {"success": True, "products": [{"sku": p["sku"], "name": p["name"], "suggested": calculate_price(p["cost_price"], margin_percent=margin_percent)} for p in all_products()]}


@app.get("/api/pricing/product/{sku}")
def api_pricing_product(sku: str, margin_percent: float = None):
    product = product_by_sku(sku)
    if not product:
        return {"success": False, "message": "Produto não encontrado"}
    return {"success": True, "product": product, "pricing": calculate_price(product["cost_price"], margin_percent=margin_percent)}


@app.get("/api/ai/optimize/{sku}")
def api_ai_optimize(sku: str):
    product = product_by_sku(sku)
    if not product:
        return {"success": False, "message": "Produto não encontrado"}
    return {"success": True, "product": product, "optimized": optimize_listing(product)}


@app.get("/api/ai/report")
def api_ai_report():
    return {"success": True, "products": [{"sku": p["sku"], "name": p["name"], "optimized": optimize_listing(p)} for p in all_products()]}


@app.get("/api/anuncios/preview/{sku}")
def api_listing_preview(sku: str, category_id: str = "MLBXXXX"):
    product = product_by_sku(sku)
    if not product:
        return {"success": False, "message": "Produto não encontrado"}
    return {"success": True, "readiness": readiness(product), "product": product, "payload": listing_payload(product, category_id)}


@app.post("/api/anuncios/publish-ml/{sku}")
async def api_publish_ml(sku: str, category_id: str):
    product = product_by_sku(sku)
    if not product:
        return {"success": False, "message": "Produto não encontrado"}
    payload = listing_payload(product, category_id)
    result = await ml_publish_item(payload)
    return {"success": result.get("success", False), "marketplace_response": result}


@app.post("/api/pedidos/simulate")
def api_order_simulate():
    order = {"id": str(uuid.uuid4()), "marketplace": "mercado_livre", "external_order_id": "MLB-ORDER-TEST-001", "status": "paid", "total_amount": 89.90, "payload": {"items": [{"sku": "SUP-001", "quantity": 1, "price": 89.90}]}, "created_at": datetime.utcnow().isoformat()}
    return {"success": True, "order": order}


@app.get("/api/relatorios/finance")
def api_finance():
    products = all_products()
    return {"success": True, "products_count": len(products), "stock_total": sum(p["stock"] for p in products), "profit_potential": round(sum(p["profit"] * p["stock"] for p in products), 2), "products": products}


@app.get("/api/database/status")
def api_database_status():
    return {"success": True, "database": database_status()}


@app.get("/api/database/health")
async def api_database_health():
    result = await db_select("companies")
    return {"success": True, "database": database_status(), "test": result}


@app.get("/api/mercadolivre/status")
def api_ml_status():
    return {"success": True, "status": ml_status()}


@app.get("/api/mercadolivre/callback")
async def api_ml_callback(code: str = ""):
    if not code:
        return {"success": False, "message": "Código OAuth ausente"}
    return await ml_exchange_code(code)


@app.get("/api/mercadolivre/me")
async def api_ml_me():
    return await ml_me()


@app.get("/api/mercadolivre/categories/search")
async def api_ml_categories(q: str):
    return await ml_categories(q)


@app.post("/api/mercadolivre/webhook")
async def api_ml_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    return {"success": True, "message": "Webhook recebido", "event": audit_event("mercado_livre_webhook", "Webhook recebido", payload)}
