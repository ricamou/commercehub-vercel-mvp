
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from urllib.parse import urlencode
from datetime import datetime
import os
import uuid

try:
    import httpx
except Exception:
    httpx = None

app = FastAPI(title="CommerceHub", version="final-vercel-1.0")


def env(name, default=""):
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
ML_TOKEN_EXPIRES_IN = env("ML_TOKEN_EXPIRES_IN")
ML_USER_ID = env("ML_USER_ID")

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


def calculate_price(cost_price):
    cost_price = float(cost_price or 0)
    desired_profit = cost_price * DEFAULT_MARGIN_PERCENT / 100
    variable_fee = ML_COMMISSION_PERCENT / 100
    sale_price = (cost_price + FIXED_OPERATIONAL_COST + desired_profit) / (1 - variable_fee)
    rounded = int(sale_price) + 0.90
    if rounded < sale_price:
        rounded += 1
    commission = rounded * variable_fee
    profit = rounded - cost_price - FIXED_OPERATIONAL_COST - commission
    margin = (profit / rounded * 100) if rounded else 0
    return {
        "sale_price": round(rounded, 2),
        "commission": round(commission, 2),
        "profit": round(profit, 2),
        "margin_percent": round(margin, 2),
        "status": "healthy" if profit > 0 and margin >= 18 else "attention"
    }


def products():
    return [{**p, **calculate_price(p["cost_price"])} for p in MOCK_PRODUCTS]


def stock_status(stock):
    stock = int(stock or 0)
    if stock <= 0:
        return "out_of_stock"
    if stock <= 3:
        return "low_stock"
    return "available"


def ai_enrich(product):
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


def listing_payload(product, category_id):
    enriched = ai_enrich(product)
    return {
        "title": enriched["title"],
        "category_id": category_id or "MLBXXXX",
        "price": product["sale_price"],
        "currency_id": "BRL",
        "available_quantity": product["stock"],
        "buying_mode": "buy_it_now",
        "listing_type_id": "gold_special",
        "condition": "new",
        "seller_custom_field": product["sku"],
        "pictures": [{"source": "https://via.placeholder.com/800"}],
        "attributes": [
            {"id": "BRAND", "value_name": product["brand"]},
            {"id": "GTIN", "value_name": product["ean"]}
        ],
        "description": enriched["description"]
    }


def layout(title, body):
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · CommerceHub</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:#f4f7fb;color:#111827}}
aside{{position:fixed;left:0;top:0;bottom:0;width:230px;background:#0b1220;color:white;padding:22px 16px}}
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
<div class="logo"><b>CH</b><div><strong>CommerceHub</strong><span>Final Vercel</span></div></div>
<nav>
<a href="/dashboard">Dashboard</a>
<a href="/mercado-livre">Mercado Livre</a>
<a href="/fornecedores">Fornecedores</a>
<a href="/produtos">Produtos</a>
<a href="/anuncios">Anúncios</a>
<a href="/pedidos">Pedidos</a>
<a href="/relatorios">Relatórios</a>
<a href="/arquitetura">Arquitetura</a>
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
    ps = products()
    stock = sum(p["stock"] for p in ps)
    cost = sum(p["cost_price"] * p["stock"] for p in ps)
    profit = sum(p["profit"] * p["stock"] for p in ps)
    body = f"""
<section class="grid">
<div class="card"><span>Produtos</span><strong>{len(ps)}</strong></div>
<div class="card"><span>Estoque total</span><strong>{stock}</strong></div>
<div class="card"><span>Custo estoque</span><strong>R$ {cost:,.2f}</strong></div>
<div class="card"><span>Lucro potencial</span><strong>R$ {profit:,.2f}</strong></div>
</section>
<section class="panel">
<h2>Status</h2>
<p><b>Mercado Livre configurado:</b> {bool(ML_CLIENT_ID and ML_CLIENT_SECRET)}</p>
<p><b>Mercado Livre conectado:</b> {bool(ML_ACCESS_TOKEN)}</p>
<p><b>Versão:</b> CommerceHub Final Vercel 1.0</p>
</section>
"""
    return layout("Dashboard", body)


@app.get("/mercado-livre", response_class=HTMLResponse)
def mercado_livre():
    auth_url = ""
    if ML_CLIENT_ID and ML_REDIRECT_URI:
        auth_url = "https://auth.mercadolivre.com.br/authorization?" + urlencode({
            "response_type": "code",
            "client_id": ML_CLIENT_ID,
            "redirect_uri": ML_REDIRECT_URI
        })
    body = f"""
<section class="panel">
<h2>Status Mercado Livre</h2>
<p><b>Client ID:</b> {bool(ML_CLIENT_ID)}</p>
<p><b>Client Secret:</b> {bool(ML_CLIENT_SECRET)}</p>
<p><b>Redirect URI:</b> {ML_REDIRECT_URI}</p>
<p><b>Access Token:</b> {bool(ML_ACCESS_TOKEN)}</p>
<p><b>User ID:</b> {ML_USER_ID or 'None'}</p>
{f'<a class="btn" href="{auth_url}">Conectar ao Mercado Livre</a>' if auth_url else '<p>Configure ML_CLIENT_ID e ML_CLIENT_SECRET na Vercel.</p>'}
<p><b>Webhook:</b> {APP_URL}/api/mercadolivre/webhook</p>
</section>
<section class="panel">
<h2>Rotas úteis</h2>
<pre>/api/mercadolivre/status
/api/mercadolivre/me
/api/mercadolivre/categories/search?q=suporte celular</pre>
</section>
"""
    return layout("Mercado Livre", body)


@app.get("/fornecedores", response_class=HTMLResponse)
def fornecedores():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{p['name']}</td><td>R$ {p['cost_price']:.2f}</td><td>R$ {p['sale_price']:.2f}</td><td>{p['stock']}</td></tr>" for p in products()])
    return layout("Fornecedores", f"<section class='panel'><h2>Fornecedor simulado</h2><table><tr><th>SKU</th><th>Produto</th><th>Custo</th><th>Preço sugerido</th><th>Estoque</th></tr>{rows}</table></section>")


@app.get("/produtos", response_class=HTMLResponse)
def produtos():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{p['name']}</td><td>{p['brand']}</td><td>{stock_status(p['stock'])}</td><td>R$ {p['sale_price']:.2f}</td></tr>" for p in products()])
    return layout("Produtos", f"<section class='panel'><h2>Catálogo</h2><table><tr><th>SKU</th><th>Produto</th><th>Marca</th><th>Estoque</th><th>Preço</th></tr>{rows}</table></section>")


@app.get("/anuncios", response_class=HTMLResponse)
def anuncios():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{p['name']}</td><td><code>/api/anuncios/preview/{p['sku']}?category_id=MLBXXXX</code></td></tr>" for p in products()])
    return layout("Anúncios", f"<section class='panel'><h2>Preview de anúncios</h2><table><tr><th>SKU</th><th>Produto</th><th>Endpoint</th></tr>{rows}</table></section>")


@app.get("/pedidos", response_class=HTMLResponse)
def pedidos():
    return layout("Pedidos", "<section class='panel'><h2>Pedidos</h2><p>Simular pedido: <code>POST /api/pedidos/simulate</code></p></section>")


@app.get("/relatorios", response_class=HTMLResponse)
def relatorios():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{p['name']}</td><td>R$ {p['profit']:.2f}</td><td>{p['margin_percent']}%</td><td>{p['status']}</td></tr>" for p in products()])
    return layout("Relatórios", f"<section class='panel'><h2>Financeiro</h2><table><tr><th>SKU</th><th>Produto</th><th>Lucro</th><th>Margem</th><th>Status</th></tr>{rows}</table></section>")


@app.get("/arquitetura", response_class=HTMLResponse)
def arquitetura():
    body = """
<section class="panel">
<h2>Arquitetura final simplificada</h2>
<p>Esta versão foi feita para funcionar na Vercel e caber facilmente no GitHub Web.</p>
<pre>
api/index.py
requirements.txt
vercel.json
README.md
.env.example
</pre>
</section>
"""
    return layout("Arquitetura", body)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "commercehub", "version": "final-vercel-1.0"}


@app.get("/api/produtos")
def api_produtos():
    return {"success": True, "products": products()}


@app.get("/api/fornecedores/mock/products")
def api_fornecedor_products():
    return {"success": True, "products": products()}


@app.get("/api/anuncios/preview/{sku}")
def api_anuncio_preview(sku: str, category_id: str = "MLBXXXX"):
    product = next((p for p in products() if p["sku"] == sku), None)
    if not product:
        return {"success": False, "message": "Produto não encontrado"}
    return {"success": True, "product": product, "payload": listing_payload(product, category_id)}


@app.post("/api/pedidos/simulate")
def api_pedido_simulate():
    return {
        "success": True,
        "order": {
            "id": str(uuid.uuid4()),
            "marketplace": "mercado_livre",
            "external_order_id": "MLB-ORDER-TEST-001",
            "status": "paid",
            "total_amount": 89.90,
            "created_at": datetime.utcnow().isoformat()
        }
    }


@app.get("/api/relatorios/finance")
def api_finance():
    ps = products()
    return {
        "success": True,
        "products_count": len(ps),
        "stock_total": sum(p["stock"] for p in ps),
        "cost_total": round(sum(p["stock"] * p["cost_price"] for p in ps), 2),
        "profit_potential": round(sum(p["stock"] * p["profit"] for p in ps), 2),
        "products": ps
    }


@app.get("/api/mercadolivre/status")
def ml_status():
    return {
        "success": True,
        "status": {
            "client_id": bool(ML_CLIENT_ID),
            "client_secret": bool(ML_CLIENT_SECRET),
            "redirect_uri": ML_REDIRECT_URI,
            "access_token": bool(ML_ACCESS_TOKEN),
            "refresh_token": bool(ML_REFRESH_TOKEN),
            "user_id": ML_USER_ID or None
        }
    }


@app.get("/api/mercadolivre/callback")
async def ml_callback(code: str = ""):
    if not code:
        return {"success": False, "message": "Código OAuth ausente"}
    if not httpx:
        return {"success": False, "message": "httpx não instalado"}
    payload = {
        "grant_type": "authorization_code",
        "client_id": ML_CLIENT_ID,
        "client_secret": ML_CLIENT_SECRET,
        "code": code,
        "redirect_uri": ML_REDIRECT_URI
    }
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("https://api.mercadolibre.com/oauth/token", data=payload)
        try:
            data = r.json()
        except Exception:
            data = {"text": r.text}
    return {
        "success": r.status_code < 400,
        "status_code": r.status_code,
        "message": "Copie access_token, refresh_token, expires_in e user_id para as variáveis da Vercel.",
        "data": data
    }


@app.get("/api/mercadolivre/me")
async def ml_me():
    if not ML_ACCESS_TOKEN:
        return {"success": False, "message": "ML_ACCESS_TOKEN não configurado"}
    if not httpx:
        return {"success": False, "message": "httpx não instalado"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://api.mercadolibre.com/users/me", headers={"Authorization": f"Bearer {ML_ACCESS_TOKEN}"})
        try:
            data = r.json()
        except Exception:
            data = {"text": r.text}
    return {"success": r.status_code < 400, "status_code": r.status_code, "data": data}


@app.get("/api/mercadolivre/categories/search")
async def ml_categories(q: str):
    if not httpx:
        return {"success": False, "message": "httpx não instalado"}
    headers = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}"} if ML_ACCESS_TOKEN else {}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://api.mercadolibre.com/sites/MLB/domain_discovery/search", params={"q": q}, headers=headers)
        try:
            data = r.json()
        except Exception:
            data = {"text": r.text}
    return {"success": r.status_code < 400, "status_code": r.status_code, "data": data}


@app.post("/api/mercadolivre/webhook")
async def ml_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    return {"success": True, "message": "Webhook recebido", "payload": payload}
