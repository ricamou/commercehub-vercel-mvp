
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from datetime import datetime, timedelta
from urllib.parse import urlencode
import os, uuid, json, hashlib, hmac, time

try:
    import httpx
except Exception:
    httpx = None

app = FastAPI(title="CommerceHub Enterprise V2 Persistence", version="enterprise-v2-supabase-persistence")


def env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if value is None:
        return ""
    value = str(value).strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()
    return value


APP_URL = env("APP_URL", "https://commercehub-vercel-mvp.vercel.app")
APP_SECRET = env("APP_SECRET", "commercehub-dev-secret")
SUPABASE_URL = env("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = env("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_KEY = env("OPENAI_API_KEY")

ML_CLIENT_ID = env("ML_CLIENT_ID")
ML_CLIENT_SECRET = env("ML_CLIENT_SECRET")
ML_REDIRECT_URI = env("ML_REDIRECT_URI", f"{APP_URL}/mercadolivre/callback")
ML_ACCESS_TOKEN = env("ML_ACCESS_TOKEN")
ML_REFRESH_TOKEN = env("ML_REFRESH_TOKEN")
ML_USER_ID = env("ML_USER_ID")

DEFAULT_MARGIN_PERCENT = float(env("DEFAULT_MARGIN_PERCENT", "35") or 35)
ML_COMMISSION_PERCENT = float(env("ML_COMMISSION_PERCENT", "16") or 16)
FIXED_OPERATIONAL_COST = float(env("FIXED_OPERATIONAL_COST", "6") or 6)


# =========================================================
# DEMO DATA / FALLBACK
# =========================================================

DEMO_COMPANY = {"id": "demo-company", "name": "CommerceHub Demo", "plan": "enterprise", "status": "active"}
DEMO_USER = {"id": "owner", "name": "Ricardo Moura", "email": "owner@commercehub.local", "role": "owner", "company_id": DEMO_COMPANY["id"]}

DEMO_SUPPLIERS = [
    {"id": "sup-001", "company_id": DEMO_COMPANY["id"], "name": "Fornecedor Simulado", "type": "api", "status": "active"},
    {"id": "sup-002", "company_id": DEMO_COMPANY["id"], "name": "Fornecedor CSV/XML", "type": "file", "status": "ready"},
]

DEMO_PRODUCTS = [
    {"id":"p1","company_id":DEMO_COMPANY["id"],"supplier_id":"sup-001","sku":"SUP-001","name":"Suporte Veicular Para Celular","brand":"MockAuto","ean":"7890000000011","category":"Acessórios Automotivos","description":"Suporte veicular para celular.","cost_price":22.90,"stock":50,"status":"active"},
    {"id":"p2","company_id":DEMO_COMPANY["id"],"supplier_id":"sup-001","sku":"SUP-002","name":"Cabo USB-C Reforçado 1 Metro","brand":"MockTech","ean":"7890000000028","category":"Acessórios para Celular","description":"Cabo USB-C reforçado.","cost_price":9.90,"stock":120,"status":"active"},
    {"id":"p3","company_id":DEMO_COMPANY["id"],"supplier_id":"sup-002","sku":"SUP-003","name":"Organizador Multiuso Para Cozinha","brand":"MockCasa","ean":"7890000000035","category":"Casa e Organização","description":"Organizador multiuso para cozinha.","cost_price":18.50,"stock":80,"status":"active"},
]

CACHE = {}
QUEUE = []
LOGS = []


# =========================================================
# DATABASE / SUPABASE
# =========================================================

def db_configured():
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and httpx)


def supabase_headers():
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }


async def db_select(table: str, query: str = "select=*"):
    if not db_configured():
        return {"success": False, "source": "memory", "data": []}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{SUPABASE_URL}/rest/v1/{table}?{query}", headers=supabase_headers())
    return {"success": r.status_code < 400, "status_code": r.status_code, "data": r.json() if r.content else [], "error": r.text if r.status_code >= 400 else ""}


async def db_insert(table: str, payload):
    if not db_configured():
        return {"success": True, "source": "memory", "data": payload}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=supabase_headers(), json=payload)
    return {"success": r.status_code < 400, "status_code": r.status_code, "data": r.json() if r.content else None, "error": r.text if r.status_code >= 400 else ""}


async def db_upsert(table: str, payload, conflict: str = "id"):
    if not db_configured():
        return {"success": True, "source": "memory", "data": payload}
    h = supabase_headers()
    h["Prefer"] = "resolution=merge-duplicates,return=representation"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={conflict}", headers=h, json=payload)
    return {"success": r.status_code < 400, "status_code": r.status_code, "data": r.json() if r.content else None, "error": r.text if r.status_code >= 400 else ""}


def add_log(event_type, message, payload=None, company_id="demo-company"):
    event = {"id": str(uuid.uuid4()), "company_id": company_id, "event_type": event_type, "message": message, "payload": payload or {}, "created_at": datetime.utcnow().isoformat()}
    LOGS.insert(0, event)
    return event


async def save_log(event_type, message, payload=None, company_id="demo-company"):
    event = add_log(event_type, message, payload, company_id)
    await db_insert("events", event)
    return event


# =========================================================
# AUTH / USERS / MULTIEMPRESA
# =========================================================

def make_token(user_id: str, company_id: str):
    exp = int(time.time()) + 60 * 60 * 24
    payload = f"{user_id}:{company_id}:{exp}"
    sig = hmac.new(APP_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_token(token: str):
    try:
        user_id, company_id, exp, sig = token.split(":")
        payload = f"{user_id}:{company_id}:{exp}"
        expected = hmac.new(APP_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected) or int(exp) < int(time.time()):
            return None
        return {"user_id": user_id, "company_id": company_id}
    except Exception:
        return None


def current_company_id(request: Request = None):
    return DEMO_COMPANY["id"]


# =========================================================
# PRICING / STOCK / AI
# =========================================================

def calculate_price(cost_price, margin_percent=None, commission_percent=None, fixed_cost=None):
    cost_price = float(cost_price or 0)
    margin_percent = float(DEFAULT_MARGIN_PERCENT if margin_percent is None else margin_percent)
    commission_percent = float(ML_COMMISSION_PERCENT if commission_percent is None else commission_percent)
    fixed_cost = float(FIXED_OPERATIONAL_COST if fixed_cost is None else fixed_cost)
    variable_fee = commission_percent / 100
    desired_profit = cost_price * margin_percent / 100
    sale_price = (cost_price + fixed_cost + desired_profit) / max(0.01, (1 - variable_fee))
    rounded = int(sale_price) + 0.90
    if rounded < sale_price:
        rounded += 1
    commission = rounded * variable_fee
    profit = rounded - cost_price - fixed_cost - commission
    margin = (profit / rounded * 100) if rounded else 0
    status = "healthy" if margin >= 18 else "attention" if margin > 0 else "loss"
    return {"cost_price": round(cost_price,2), "sale_price": round(rounded,2), "commission": round(commission,2), "profit": round(profit,2), "margin_percent": round(margin,2), "status": status}


def with_price(product):
    return {**product, **calculate_price(product.get("cost_price", 0))}


def demo_products():
    return [with_price(p) for p in DEMO_PRODUCTS]


def stock_status(stock):
    stock = int(stock or 0)
    if stock <= 0: return "out_of_stock"
    if stock <= 5: return "low_stock"
    return "available"


def ai_title(product):
    title = f"{product.get('brand','')} {product.get('name','')} {product.get('category','')}".strip()
    return " ".join(title.split())[:60]


def ai_description(product):
    return "\n".join([
        f"Produto: {product.get('name','')}",
        f"Marca: {product.get('brand','')}",
        f"Categoria: {product.get('category','')}",
        f"EAN: {product.get('ean','')}",
        f"Descrição: {product.get('description','Produto disponível para venda.')}",
        "Produto novo. Confirme categoria, atributos e estoque antes da publicação."
    ])


def ai_seo(product):
    title = ai_title(product)
    keywords = [w.lower() for w in title.replace("-", " ").split() if len(w) > 2]
    score = 100 if len(title) >= 25 and len(keywords) >= 3 else 70
    return {"title": title, "description": ai_description(product), "keywords": keywords[:12], "seo_score": score}


def listing_payload(product, category_id="MLBXXXX"):
    optimized = ai_seo(product)
    return {
        "title": optimized["title"],
        "category_id": category_id,
        "price": product.get("sale_price") or calculate_price(product.get("cost_price",0))["sale_price"],
        "currency_id": "BRL",
        "available_quantity": int(product.get("stock", 0)),
        "buying_mode": "buy_it_now",
        "listing_type_id": "gold_special",
        "condition": "new",
        "seller_custom_field": product.get("sku"),
        "pictures": [{"source": product.get("image_url") or "https://via.placeholder.com/800"}],
        "attributes": [{"id": "BRAND", "value_name": product.get("brand") or "Genérico"}, {"id": "GTIN", "value_name": product.get("ean") or ""}],
        "description": optimized["description"]
    }


# =========================================================
# MARKETPLACES
# =========================================================

def marketplace_status():
    return [
        {"marketplace": "mercado_livre", "status": "active", "connected": bool(ML_ACCESS_TOKEN and ML_REFRESH_TOKEN)},
        {"marketplace": "shopee", "status": "prepared", "connected": False},
        {"marketplace": "amazon", "status": "prepared", "connected": False},
        {"marketplace": "magalu", "status": "prepared", "connected": False},
    ]


async def oauth_get_token():
    fallback = {"access_token": ML_ACCESS_TOKEN, "refresh_token": ML_REFRESH_TOKEN, "user_id": ML_USER_ID, "source": "env"}
    if not db_configured():
        return fallback
    res = await db_select("oauth_tokens", "marketplace=eq.mercado_livre&select=*&limit=1")
    if res.get("success") and res.get("data"):
        t = res["data"][0]
        return {"access_token": t.get("access_token") or ML_ACCESS_TOKEN, "refresh_token": t.get("refresh_token") or ML_REFRESH_TOKEN, "user_id": t.get("user_id") or ML_USER_ID, "source": "supabase"}
    return fallback


async def oauth_save_token(data):
    token = {"marketplace": "mercado_livre", "access_token": data.get("access_token",""), "refresh_token": data.get("refresh_token",""), "user_id": str(data.get("user_id","")), "expires_in": int(data.get("expires_in") or 0), "token_type": data.get("token_type","Bearer"), "scope": data.get("scope",""), "updated_at": datetime.utcnow().isoformat()}
    return await db_upsert("oauth_tokens", token, "marketplace")


def ml_auth_url():
    if not ML_CLIENT_ID:
        return ""
    return "https://auth.mercadolivre.com.br/authorization?" + urlencode({"response_type": "code", "client_id": ML_CLIENT_ID, "redirect_uri": ML_REDIRECT_URI})


async def ml_exchange_code(code):
    if not httpx:
        return {"success": False, "message": "httpx não instalado"}
    payload = {"grant_type":"authorization_code", "client_id":ML_CLIENT_ID, "client_secret":ML_CLIENT_SECRET, "code":code, "redirect_uri":ML_REDIRECT_URI}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post("https://api.mercadolibre.com/oauth/token", data=payload)
    data = r.json() if r.content else {}
    if r.status_code < 400:
        await oauth_save_token(data)
    return {"success": r.status_code < 400, "status_code": r.status_code, "data": data}


async def ml_refresh_token():
    token = await oauth_get_token()
    refresh = token.get("refresh_token")
    if not refresh:
        return {"success": False, "message": "Refresh token ausente"}
    payload = {"grant_type": "refresh_token", "client_id": ML_CLIENT_ID, "client_secret": ML_CLIENT_SECRET, "refresh_token": refresh}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post("https://api.mercadolibre.com/oauth/token", data=payload)
    data = r.json() if r.content else {}
    save = None
    if r.status_code < 400:
        save = await oauth_save_token(data)
    return {"success": r.status_code < 400, "status_code": r.status_code, "data": data, "save": save}


async def ml_request(method, path, params=None, payload=None):
    token = await oauth_get_token()
    access = token.get("access_token")
    if not access:
        return {"success": False, "message": "Access token ausente"}
    headers = {"Authorization": f"Bearer {access}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.request(method, "https://api.mercadolibre.com"+path, params=params or {}, json=payload, headers=headers)
    if r.status_code == 401:
        refreshed = await ml_refresh_token()
        if not refreshed.get("success"):
            return {"success": False, "status_code": 401, "refresh": refreshed}
        access = refreshed["data"].get("access_token")
        headers = {"Authorization": f"Bearer {access}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.request(method, "https://api.mercadolibre.com"+path, params=params or {}, json=payload, headers=headers)
    return {"success": r.status_code < 400, "status_code": r.status_code, "data": r.json() if r.content else {}}


async def ml_me():
    return await ml_request("GET", "/users/me")


async def ml_items(limit=20, offset=0):
    me = await ml_me()
    if not me.get("success"):
        return me
    user_id = me["data"].get("id") or ML_USER_ID
    return await ml_request("GET", f"/users/{user_id}/items/search", {"limit": limit, "offset": offset})


async def ml_orders(limit=20, offset=0):
    me = await ml_me()
    if not me.get("success"):
        return me
    seller_id = me["data"].get("id") or ML_USER_ID
    return await ml_request("GET", "/orders/search", {"seller": seller_id, "limit": limit, "offset": offset})


# =========================================================
# QUEUE / CACHE / SYNC / WEBHOOK
# =========================================================

def cache_get(key):
    item = CACHE.get(key)
    if not item: return None
    if item["expires_at"] < time.time():
        CACHE.pop(key, None)
        return None
    return item["value"]


def cache_set(key, value, ttl=300):
    CACHE[key] = {"value": value, "expires_at": time.time()+ttl}
    return value


def enqueue(job_type, payload):
    job = {"id": str(uuid.uuid4()), "type": job_type, "payload": payload, "status": "queued", "created_at": datetime.utcnow().isoformat()}
    QUEUE.append(job)
    add_log("queue", f"Job enfileirado: {job_type}", job)
    return job


async def process_queue():
    processed = []
    for job in QUEUE:
        if job["status"] != "queued":
            continue
        job["status"] = "processing"
        if job["type"] == "sync_inventory":
            job["result"] = {"success": True, "message": "Estoque sincronizado em modo demo."}
        elif job["type"] == "sync_prices":
            job["result"] = {"success": True, "message": "Preços recalculados em modo demo."}
        elif job["type"] == "ml_refresh":
            job["result"] = await ml_refresh_token()
        else:
            job["result"] = {"success": True, "message": "Job processado."}
        job["status"] = "done"
        job["processed_at"] = datetime.utcnow().isoformat()
        processed.append(job)
    return {"success": True, "processed": processed, "queue_size": len(QUEUE)}


async def full_sync():
    enqueue("sync_inventory", {"company_id": DEMO_COMPANY["id"]})
    enqueue("sync_prices", {"company_id": DEMO_COMPANY["id"]})
    result = await process_queue()
    add_log("sync", "Sincronização completa executada", result)
    return result


# =========================================================
# UI
# =========================================================

def layout(title, body):
    return f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{title} · CommerceHub V2</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:#f4f7fb;color:#111827}}
aside{{position:fixed;left:0;top:0;bottom:0;width:240px;background:#0b1220;color:white;padding:22px 14px;overflow:auto}}
.logo{{display:flex;gap:10px;align-items:center;margin-bottom:26px}}.logo b{{background:#2563eb;padding:12px;border-radius:10px}}.logo span{{display:block;color:#9ca3af;font-size:12px}}
nav a{{display:block;color:white;text-decoration:none;padding:9px;border-radius:8px;margin:3px 0}}nav a:hover{{background:#172033}}
main{{margin-left:240px;padding:28px}}h1{{font-size:32px;margin:0}}header p{{color:#64748b}}
.grid{{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:16px;margin:22px 0}}.card,.panel{{background:white;border:1px solid #d8dee8;border-radius:16px;box-shadow:0 8px 24px rgba(15,23,42,.05)}}
.card{{padding:20px}}.card span{{display:block;color:#64748b}}.card strong{{font-size:28px;display:block;margin-top:10px}}
.panel{{padding:22px;margin:18px 0}}table{{width:100%;border-collapse:collapse;margin-top:12px}}th,td{{padding:11px;border-bottom:1px solid #e5e7eb;text-align:left}}th{{background:#f8fafc}}
pre{{background:#0b1220;color:white;padding:14px;border-radius:10px;overflow:auto}}code{{background:#eef2ff;padding:3px 6px;border-radius:6px}}.btn{{display:inline-block;background:#2563eb;color:white;text-decoration:none;padding:10px 14px;border-radius:10px;margin:6px 4px 6px 0}}
.ok{{color:#16a34a;font-weight:bold}}.bad{{color:#dc2626;font-weight:bold}}
</style></head><body><aside>
<div class='logo'><b>CH</b><div><strong>CommerceHub</strong><span>Enterprise V2 Persistence</span></div></div>
<nav>
<a href='/'>Dashboard</a><a href='/auth'>Login</a><a href='/persistence'>Persistência</a><a href='/companies'>Multiempresa</a><a href='/suppliers'>Fornecedores</a><a href='/products'>Produtos</a><a href='/inventory'>Estoque</a><a href='/marketplaces'>Marketplaces</a><a href='/mercado-livre'>Mercado Livre</a><a href='/ai'>IA</a><a href='/reports'>Relatórios</a><a href='/logs'>Logs</a><a href='/queue'>Filas</a><a href='/cache'>Cache</a><a href='/webhooks'>Webhooks</a><a href='/sync'>Sync Tempo Real</a><a href='/api/health' target='_blank'>API Health</a>
</nav></aside><main><header><h1>{title}</h1><p>Fornecedor → CommerceHub → Marketplaces → Cliente</p></header>{body}</main></body></html>"""


def btn(path, label):
    return f"<a class='btn' href='{path}' target='_blank'>{label}</a>"


# =========================================================
# PAGES
# =========================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    products = demo_products()
    ml = await ml_items(10, 0) if ML_ACCESS_TOKEN else {"success": False}
    orders = await ml_orders(10, 0) if ML_ACCESS_TOKEN else {"success": False}
    item_total = ml.get("data", {}).get("paging", {}).get("total", 0) if ml.get("success") else 0
    order_total = orders.get("data", {}).get("paging", {}).get("total", 0) if orders.get("success") else 0
    body = f"""
<section class='grid'>
<div class='card'><span>Empresas</span><strong>1</strong></div>
<div class='card'><span>Produtos</span><strong>{len(products)}</strong></div>
<div class='card'><span>Anúncios ML</span><strong>{item_total}</strong></div>
<div class='card'><span>Pedidos ML</span><strong>{order_total}</strong></div>
</section>
<section class='panel'><h2>CommerceHub Enterprise V2 Persistence</h2><p>Sistema comercial com banco, login, multiempresa, marketplaces, IA, filas, cache, webhooks e sincronização.</p>{btn('/api/enterprise/status','Status JSON')}</section>
"""
    return layout("Dashboard Profissional", body)




@app.get("/persistence", response_class=HTMLResponse)
def persistence_page():
    body = f"""
<section class='panel'>
<h2>Persistência Supabase</h2>
<p>Modo atual: <b>{persistence_mode()}</b></p>
<table>
<tr><th>Item</th><th>Endpoint</th></tr>
<tr><td>Status</td><td><code>/api/persistence/status</code></td></tr>
<tr><td>Seed inicial</td><td><code>POST /api/persistence/seed</code></td></tr>
<tr><td>Salvar token ML</td><td><code>POST /api/persistence/token</code></td></tr>
<tr><td>Produtos salvos</td><td><code>/api/db/products</code></td></tr>
<tr><td>Fornecedores salvos</td><td><code>/api/db/suppliers</code></td></tr>
<tr><td>Estoque salvo</td><td><code>/api/db/inventory_movements</code></td></tr>
<tr><td>Logs salvos</td><td><code>/api/db/events</code></td></tr>
<tr><td>Pedidos/Webhooks salvos</td><td><code>/api/db/orders</code></td></tr>
<tr><td>Tokens salvos</td><td><code>/api/db/oauth_tokens</code></td></tr>
</table>
<p><a class='btn' href='/api/persistence/status' target='_blank'>Status</a>
<a class='btn' href='/api/db/products' target='_blank'>Produtos no banco</a>
<a class='btn' href='/api/db/events' target='_blank'>Logs no banco</a></p>
</section>
"""
    return layout("Persistência Supabase", body)


@app.get("/auth", response_class=HTMLResponse)
def auth_page():
    token = make_token(DEMO_USER["id"], DEMO_COMPANY["id"])
    return layout("Login de usuários", f"<section class='panel'><h2>Login pronto</h2><p>Usuário demo:</p><pre>{DEMO_USER}</pre><p>Token demo:</p><pre>{token}</pre>{btn('/api/auth/me?token='+token,'Validar token')}</section>")


@app.get("/companies", response_class=HTMLResponse)
def companies_page():
    return layout("Multiempresa", f"<section class='panel'><h2>Empresas</h2><table><tr><th>ID</th><th>Nome</th><th>Plano</th><th>Status</th></tr><tr><td>{DEMO_COMPANY['id']}</td><td>{DEMO_COMPANY['name']}</td><td>{DEMO_COMPANY['plan']}</td><td>{DEMO_COMPANY['status']}</td></tr></table></section>")


@app.get("/suppliers", response_class=HTMLResponse)
def suppliers_page():
    rows = "".join([f"<tr><td>{s['id']}</td><td>{s['name']}</td><td>{s['type']}</td><td>{s['status']}</td></tr>" for s in DEMO_SUPPLIERS])
    return layout("Cadastro de fornecedores", f"<section class='panel'><h2>Fornecedores</h2><table><tr><th>ID</th><th>Nome</th><th>Tipo</th><th>Status</th></tr>{rows}</table>{btn('/api/suppliers','API Fornecedores')}</section>")


@app.get("/products", response_class=HTMLResponse)
def products_page():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{p['name']}</td><td>{p['brand']}</td><td>{p['stock']}</td><td>R$ {p['sale_price']:.2f}</td></tr>" for p in demo_products()])
    return layout("Cadastro de produtos", f"<section class='panel'><h2>Produtos</h2><table><tr><th>SKU</th><th>Produto</th><th>Marca</th><th>Estoque</th><th>Preço</th></tr>{rows}</table>{btn('/api/products','API Produtos')}</section>")


@app.get("/inventory", response_class=HTMLResponse)
def inventory_page():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{p['name']}</td><td>{p['stock']}</td><td>{stock_status(p['stock'])}</td></tr>" for p in demo_products()])
    return layout("Estoque", f"<section class='panel'><h2>Estoque</h2><table><tr><th>SKU</th><th>Produto</th><th>Qtd</th><th>Status</th></tr>{rows}</table>{btn('/api/inventory','API Estoque')}</section>")


@app.get("/marketplaces", response_class=HTMLResponse)
def marketplaces_page():
    rows = "".join([f"<tr><td>{m['marketplace']}</td><td>{m['status']}</td><td>{m['connected']}</td></tr>" for m in marketplace_status()])
    return layout("Marketplaces", f"<section class='panel'><h2>Hub de Marketplaces</h2><table><tr><th>Marketplace</th><th>Status</th><th>Conectado</th></tr>{rows}</table></section>")


@app.get("/mercado-livre", response_class=HTMLResponse)
def mercado_livre_page():
    connected = bool(ML_ACCESS_TOKEN and ML_REFRESH_TOKEN)
    auth = ml_auth_url()
    html = f"<section class='panel'><h2>Mercado Livre</h2><p class='{'ok' if connected else 'bad'}'>{'CONECTADO' if connected else 'NÃO CONECTADO'}</p>"
    html += btn(auth, "Conectar Mercado Livre") if auth and not connected else ""
    html += btn('/api/mercadolivre/me','Testar Conta') + btn('/api/ml/items','Anúncios') + btn('/api/ml/orders','Pedidos') + "</section>"
    return layout("Mercado Livre", html)


@app.get("/ai", response_class=HTMLResponse)
def ai_page():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{ai_title(p)}</td><td>{ai_seo(p)['seo_score']}%</td><td>R$ {calculate_price(p['cost_price'])['sale_price']:.2f}</td></tr>" for p in demo_products()])
    return layout("IA", f"<section class='panel'><h2>IA para descrição, preço e SEO</h2><table><tr><th>SKU</th><th>Título IA</th><th>SEO</th><th>Preço IA</th></tr>{rows}</table>{btn('/api/ai/report','API IA')}</section>")


@app.get("/reports", response_class=HTMLResponse)
def reports_page():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{p['name']}</td><td>R$ {p['profit']:.2f}</td><td>{p['margin_percent']}%</td></tr>" for p in demo_products()])
    return layout("Relatórios", f"<section class='panel'><h2>Relatórios Financeiros</h2><table><tr><th>SKU</th><th>Produto</th><th>Lucro</th><th>Margem</th></tr>{rows}</table>{btn('/api/reports/finance','API Relatórios')}</section>")


@app.get("/logs", response_class=HTMLResponse)
def logs_page():
    rows = "".join([f"<tr><td>{l['created_at']}</td><td>{l['event_type']}</td><td>{l['message']}</td></tr>" for l in LOGS[:30]])
    return layout("Logs", f"<section class='panel'><h2>Logs e Auditoria</h2><table><tr><th>Data</th><th>Tipo</th><th>Mensagem</th></tr>{rows}</table>{btn('/api/logs','API Logs')}</section>")


@app.get("/queue", response_class=HTMLResponse)
def queue_page():
    rows = "".join([f"<tr><td>{j['id']}</td><td>{j['type']}</td><td>{j['status']}</td></tr>" for j in QUEUE])
    return layout("Filas", f"<section class='panel'><h2>Filas</h2><p>Jobs assíncronos para sincronização.</p><table><tr><th>ID</th><th>Tipo</th><th>Status</th></tr>{rows}</table>{btn('/api/queue/process','Processar fila')}</section>")


@app.get("/cache", response_class=HTMLResponse)
def cache_page():
    rows = "".join([f"<tr><td>{k}</td><td>{round(v['expires_at']-time.time(),0)}s</td></tr>" for k,v in CACHE.items()])
    return layout("Cache", f"<section class='panel'><h2>Cache</h2><table><tr><th>Chave</th><th>Expira em</th></tr>{rows}</table>{btn('/api/cache/status','API Cache')}</section>")


@app.get("/webhooks", response_class=HTMLResponse)
def webhooks_page():
    return layout("Webhooks", f"<section class='panel'><h2>Webhooks</h2><p>Endpoint Mercado Livre:</p><pre>{APP_URL}/api/webhooks/mercadolivre</pre>{btn('/api/webhooks/status','API Webhooks')}</section>")


@app.get("/sync", response_class=HTMLResponse)
def sync_page():
    return layout("Sincronização em tempo real", f"<section class='panel'><h2>Sync Realtime</h2><p>Sincronização via fila, webhooks e jobs.</p>{btn('/api/sync/run','Executar sincronização')}</section>")


@app.get("/mercadolivre/callback", response_class=HTMLResponse)
async def ml_callback(code: str = ""):
    if not code:
        return layout("Mercado Livre Callback", "<section class='panel'><h2>Erro</h2><p>Código ausente.</p></section>")
    result = await ml_exchange_code(code)
    return layout("Mercado Livre Conectado", f"<section class='panel'><h2>Resultado da conexão</h2><pre>{result}</pre>{btn('/api/mercadolivre/me','Testar Conta')}</section>")



# =========================================================
# SUPABASE PERSISTENCE V2
# =========================================================

def persistence_mode():
    return "supabase" if db_configured() else "memory"


async def seed_company():
    payload = {
        "id": DEMO_COMPANY["id"],
        "name": DEMO_COMPANY["name"],
        "plan": DEMO_COMPANY["plan"],
        "status": DEMO_COMPANY["status"]
    }
    return await db_upsert("companies", payload, "id")


async def persist_supplier(payload: dict):
    supplier = {
        "id": payload.get("id") or str(uuid.uuid4()),
        "company_id": payload.get("company_id") or DEMO_COMPANY["id"],
        "name": payload.get("name") or "Fornecedor sem nome",
        "type": payload.get("type") or "manual",
        "status": payload.get("status") or "active",
        "config": payload.get("config") or {}
    }
    await seed_company()
    result = await db_upsert("suppliers", supplier, "id")
    await save_log("supplier_saved", "Fornecedor salvo no banco", supplier, supplier["company_id"])
    return {"success": True, "mode": persistence_mode(), "supplier": supplier, "db_result": result}


async def persist_product(payload: dict):
    pricing = calculate_price(payload.get("cost_price", 0))
    product = {
        "id": payload.get("id") or str(uuid.uuid4()),
        "company_id": payload.get("company_id") or DEMO_COMPANY["id"],
        "supplier_id": payload.get("supplier_id"),
        "sku": payload.get("sku") or f"SKU-{str(uuid.uuid4())[:8]}",
        "name": payload.get("name") or "Produto sem nome",
        "brand": payload.get("brand") or "",
        "ean": payload.get("ean") or "",
        "category": payload.get("category") or "",
        "description": payload.get("description") or "",
        "cost_price": float(payload.get("cost_price") or 0),
        "sale_price": float(payload.get("sale_price") or pricing["sale_price"]),
        "stock": int(payload.get("stock") or 0),
        "status": payload.get("status") or "active",
        "raw_data": payload.get("raw_data") or payload
    }
    await seed_company()
    result = await db_upsert("products", product, "id")
    await save_log("product_saved", "Produto salvo no banco", product, product["company_id"])
    return {"success": True, "mode": persistence_mode(), "product": product, "pricing": pricing, "db_result": result}


async def persist_inventory(payload: dict):
    movement = {
        "id": payload.get("id") or str(uuid.uuid4()),
        "company_id": payload.get("company_id") or DEMO_COMPANY["id"],
        "product_id": payload.get("product_id"),
        "sku": payload.get("sku"),
        "movement_type": payload.get("movement_type") or "set",
        "quantity": int(payload.get("quantity") or payload.get("stock") or 0),
        "previous_stock": int(payload.get("previous_stock") or 0),
        "new_stock": int(payload.get("new_stock") or payload.get("stock") or payload.get("quantity") or 0),
        "source": payload.get("source") or "manual",
        "created_at": datetime.utcnow().isoformat()
    }
    await seed_company()
    result = await db_insert("inventory_movements", movement)
    await save_log("inventory_saved", "Movimento de estoque salvo no banco", movement, movement["company_id"])
    return {"success": True, "mode": persistence_mode(), "movement": movement, "db_result": result}


async def persist_order(payload: dict):
    order = {
        "id": payload.get("id") or str(uuid.uuid4()),
        "company_id": payload.get("company_id") or DEMO_COMPANY["id"],
        "marketplace": payload.get("marketplace") or "mercado_livre",
        "external_order_id": str(payload.get("external_order_id") or payload.get("id") or payload.get("resource") or ""),
        "status": payload.get("status") or "received",
        "total_amount": float(payload.get("total_amount") or payload.get("paid_amount") or 0),
        "payload": payload,
        "created_at": payload.get("created_at") or datetime.utcnow().isoformat()
    }
    await seed_company()
    result = await db_upsert("orders", order, "id")
    await save_log("order_saved", "Pedido/webhook salvo no banco", order, order["company_id"])
    return {"success": True, "mode": persistence_mode(), "order": order, "db_result": result}


async def persist_ml_token_from_env():
    if not ML_ACCESS_TOKEN and not ML_REFRESH_TOKEN:
        return {"success": False, "message": "Tokens Mercado Livre ausentes nas variáveis de ambiente."}

    data = {
        "access_token": ML_ACCESS_TOKEN,
        "refresh_token": ML_REFRESH_TOKEN,
        "user_id": ML_USER_ID,
        "expires_in": int(env("ML_TOKEN_EXPIRES_IN", "21600") or 21600),
        "token_type": "Bearer",
        "scope": "env_import"
    }
    result = await oauth_save_token(data)
    await save_log("oauth_token_saved", "Token Mercado Livre persistido", {"user_id": ML_USER_ID, "source": "env"})
    return {"success": True, "mode": persistence_mode(), "save_result": result}


async def persist_all_demo_data():
    await seed_company()
    suppliers = []
    products = []
    inventory = []

    for supplier in DEMO_SUPPLIERS:
        suppliers.append(await persist_supplier(supplier))

    for product in DEMO_PRODUCTS:
        saved = await persist_product(product)
        products.append(saved)
        inventory.append(await persist_inventory({
            "product_id": saved["product"]["id"],
            "sku": saved["product"]["sku"],
            "stock": saved["product"]["stock"],
            "source": "initial_seed"
        }))

    token = await persist_ml_token_from_env()
    event = await save_log("seed_completed", "Seed inicial persistido", {
        "suppliers": len(suppliers),
        "products": len(products),
        "inventory": len(inventory),
        "token": token.get("success")
    })

    return {
        "success": True,
        "mode": persistence_mode(),
        "company": DEMO_COMPANY,
        "suppliers": suppliers,
        "products": products,
        "inventory": inventory,
        "token": token,
        "event": event
    }


async def list_persisted(table: str):
    if not db_configured():
        return {"success": True, "mode": "memory", "message": "Supabase não configurado. Exibindo dados demo.", "data": []}
    return await db_select(table, "select=*&order=created_at.desc")



# =========================================================
# API
# =========================================================



@app.get("/api/persistence/status")
def api_persistence_status():
    return {
        "success": True,
        "mode": persistence_mode(),
        "supabase_configured": db_configured(),
        "tables": [
            "companies",
            "users_app",
            "suppliers",
            "products",
            "inventory_movements",
            "listings",
            "orders",
            "events",
            "oauth_tokens"
        ]
    }


@app.post("/api/persistence/seed")
async def api_persistence_seed():
    return await persist_all_demo_data()


@app.post("/api/persistence/token")
async def api_persistence_token():
    return await persist_ml_token_from_env()


@app.post("/api/inventory/movement")
async def api_inventory_movement(payload: dict):
    return await persist_inventory(payload)


@app.post("/api/orders/save")
async def api_orders_save(payload: dict):
    return await persist_order(payload)


@app.get("/api/db/{table}")
async def api_db_table(table: str):
    allowed = {"companies", "users_app", "suppliers", "products", "inventory_movements", "listings", "orders", "events", "oauth_tokens"}
    if table not in allowed:
        return {"success": False, "message": "Tabela não permitida."}
    result = await list_persisted(table)
    if table == "oauth_tokens" and result.get("data"):
        safe = []
        for row in result["data"]:
            row = dict(row)
            row["access_token"] = bool(row.get("access_token"))
            row["refresh_token"] = bool(row.get("refresh_token"))
            safe.append(row)
        result["data"] = safe
    return result


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "commercehub", "version": "enterprise-v2-supabase-persistence"}


@app.get("/api/enterprise/status")
def enterprise_status():
    return {"success": True, "version": "enterprise-v2-supabase-persistence", "database": "supabase" if db_configured() else "memory", "marketplaces": marketplace_status(), "features": ["supabase","login","multiempresa","fornecedores","produtos","estoque","sync","mercado_livre","shopee","amazon","magalu","ia","dashboard","relatorios","logs","filas","cache","webhooks","realtime"]}


@app.get("/api/auth/me")
def api_auth_me(token: str = ""):
    verified = verify_token(token)
    return {"success": bool(verified), "user": DEMO_USER if verified else None, "token": verified}


@app.get("/api/companies")
def api_companies():
    return {"success": True, "companies": [DEMO_COMPANY]}


@app.get("/api/suppliers")
def api_suppliers():
    return {"success": True, "suppliers": DEMO_SUPPLIERS}


@app.post("/api/suppliers")
async def api_supplier_create(payload: dict):
    return await persist_supplier(payload)


@app.get("/api/products")
def api_products():
    return {"success": True, "products": demo_products()}


@app.post("/api/products")
async def api_product_create(payload: dict):
    return await persist_product(payload)


@app.get("/api/inventory")
def api_inventory():
    return {"success": True, "inventory": [{"sku": p["sku"], "name": p["name"], "stock": p["stock"], "status": stock_status(p["stock"])} for p in demo_products()]}


@app.post("/api/inventory/sync")
async def api_inventory_sync():
    job = enqueue("sync_inventory", {"company_id": DEMO_COMPANY["id"]})
    for product in demo_products():
        await persist_inventory({"sku": product["sku"], "stock": product["stock"], "source": "sync"})
    return {"success": True, "job": job, "message": "Estoque enviado para persistência."}


@app.get("/api/pricing/report")
def api_pricing():
    return {"success": True, "pricing": [{"sku": p["sku"], "pricing": calculate_price(p["cost_price"])} for p in demo_products()]}


@app.get("/api/ai/report")
def api_ai_report():
    return {"success": True, "products": [{"sku": p["sku"], "ai": ai_seo(p), "pricing": calculate_price(p["cost_price"])} for p in demo_products()]}


@app.get("/api/reports/finance")
def api_reports_finance():
    products = demo_products()
    return {"success": True, "products": products, "total_stock": sum(p["stock"] for p in products), "profit_potential": round(sum(p["profit"]*p["stock"] for p in products),2)}


@app.get("/api/logs")
def api_logs():
    return {"success": True, "logs": LOGS}


@app.get("/api/queue/status")
def api_queue_status():
    return {"success": True, "queue": QUEUE}


@app.get("/api/queue/process")
async def api_queue_process():
    return await process_queue()


@app.get("/api/cache/status")
def api_cache_status():
    return {"success": True, "items": len(CACHE), "keys": list(CACHE.keys())}


@app.post("/api/cache/clear")
def api_cache_clear():
    CACHE.clear()
    return {"success": True}


@app.get("/api/webhooks/status")
def api_webhooks_status():
    return {"success": True, "webhooks": [{"marketplace":"mercado_livre","url":f"{APP_URL}/api/webhooks/mercadolivre","status":"ready"}]}


@app.post("/api/webhooks/mercadolivre")
async def webhook_ml(request: Request):
    payload = await request.json()
    await save_log("webhook_ml", "Webhook Mercado Livre recebido", payload)
    enqueue("webhook_process", payload)
    saved_order = await persist_order({
        "marketplace": "mercado_livre",
        "external_order_id": payload.get("id") or payload.get("resource") or str(uuid.uuid4()),
        "status": "webhook_received",
        "payload": payload
    })
    return {"success": True, "received": payload, "saved_order": saved_order}


@app.get("/api/sync/run")
async def api_sync_run():
    return await full_sync()


@app.get("/api/marketplaces")
def api_marketplaces():
    return {"success": True, "marketplaces": marketplace_status()}


@app.get("/api/mercadolivre/status")
def api_ml_status():
    return {"success": True, "connected": bool(ML_ACCESS_TOKEN and ML_REFRESH_TOKEN), "redirect_uri": ML_REDIRECT_URI, "user_id": ML_USER_ID}


@app.get("/api/mercadolivre/oauth-config")
def api_ml_oauth_config():
    return {"success": True, "auth_url": ml_auth_url(), "redirect_uri": ML_REDIRECT_URI, "has_client_id": bool(ML_CLIENT_ID), "has_client_secret": bool(ML_CLIENT_SECRET)}


@app.get("/api/mercadolivre/me")
async def api_ml_me():
    return await ml_me()


@app.get("/api/mercadolivre/refresh-token")
async def api_ml_refresh():
    return await ml_refresh_token()


@app.get("/api/ml/items")
async def api_ml_items(limit: int = 20, offset: int = 0):
    return await ml_items(limit, offset)


@app.get("/api/ml/orders")
async def api_ml_orders(limit: int = 20, offset: int = 0):
    return await ml_orders(limit, offset)


@app.get("/api/listings/preview/{sku}")
def api_listing_preview(sku: str, category_id: str = "MLBXXXX"):
    product = next((p for p in demo_products() if p["sku"] == sku), None)
    if not product:
        return {"success": False, "message": "Produto não encontrado"}
    return {"success": True, "payload": listing_payload(product, category_id), "ai": ai_seo(product)}


@app.post("/api/listings/publish-ml/{sku}")
async def api_listing_publish_ml(sku: str, category_id: str):
    product = next((p for p in demo_products() if p["sku"] == sku), None)
    if not product:
        return {"success": False, "message": "Produto não encontrado"}
    payload = listing_payload(product, category_id)
    return await ml_request("POST", "/items", payload=payload)


@app.get("/api/shopee/status")
def shopee_status():
    return {"success": True, "marketplace": "shopee", "status": "prepared", "message": "Conector preparado para credenciais reais."}


@app.get("/api/amazon/status")
def amazon_status():
    return {"success": True, "marketplace": "amazon", "status": "prepared", "message": "Conector preparado para SP-API."}


@app.get("/api/magalu/status")
def magalu_status():
    return {"success": True, "marketplace": "magalu", "status": "prepared", "message": "Conector preparado para API Magalu."}
