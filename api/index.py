
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from urllib.parse import urlencode
from datetime import datetime
import os, json, uuid, time, urllib.request, urllib.error

app = FastAPI(title="CommerceHub Enterprise Backend Reviewed Stable", version="enterprise-backend-reviewed-stable")

def env(name, default=""):
    value = os.getenv(name, default)
    if value is None:
        return ""
    value = str(value).strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()
    return value

APP_URL = env("APP_URL", "https://commercehub-vercel-mvp.vercel.app")
SUPABASE_URL = env("SUPABASE_URL") or env("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = env("SUPABASE_SERVICE_ROLE_KEY") or env("SUPABASE_KEY") or env("SUPABASE_ANON_KEY")

ML_CLIENT_ID = env("ML_CLIENT_ID")
ML_CLIENT_SECRET = env("ML_CLIENT_SECRET")
ML_REDIRECT_URI = env("ML_REDIRECT_URI", f"{APP_URL}/mercadolivre/callback")
ML_ACCESS_TOKEN = env("ML_ACCESS_TOKEN")
ML_REFRESH_TOKEN = env("ML_REFRESH_TOKEN")
ML_USER_ID = env("ML_USER_ID")

DB_TIMEOUT_SECONDS = int(env("DB_TIMEOUT_SECONDS", "6") or 6)
DB_RETRY_ATTEMPTS = int(env("DB_RETRY_ATTEMPTS", "1") or 1)

MEMORY = {
    "companies": [],
    "users": [],
    "suppliers": [],
    "products": [],
    "inventory": [],
    "orders": [],
    "listings": [],
    "oauth_tokens": [],
    "logs": [],
    "ai_history": [],
    "queue": [],
    "webhooks": [],
    "sync_jobs": [],
}

DEFAULT_COMPANY_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_SUPPLIER_ID = "00000000-0000-0000-0000-000000000101"
DEFAULT_PRODUCT_ID = "00000000-0000-0000-0000-000000001001"

def db_configured():
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)

def db_mode():
    return "supabase" if db_configured() else "memory"

def safe_json(raw, default):
    try:
        if not raw:
            return default
        return json.loads(raw)
    except Exception:
        return default

def supabase_request(method, path, payload=None, prefer="return=representation"):
    if not SUPABASE_URL:
        return {"success": False, "mode": "supabase_error", "status_code": 0, "data": [] if method == "GET" else None, "error": "SUPABASE_URL ausente"}
    if not SUPABASE_SERVICE_ROLE_KEY:
        return {"success": False, "mode": "supabase_error", "status_code": 0, "data": [] if method == "GET" else None, "error": "SUPABASE_SERVICE_ROLE_KEY ausente"}

    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{path.lstrip('/')}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method.upper(),
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        },
    )

    last_error = ""
    for attempt in range(DB_RETRY_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(req, timeout=DB_TIMEOUT_SECONDS) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                return {
                    "success": 200 <= resp.status < 400,
                    "mode": "supabase",
                    "status_code": resp.status,
                    "data": safe_json(raw, [] if method.upper() == "GET" else None),
                    "error": "",
                    "attempt": attempt + 1,
                }
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="ignore")
            return {
                "success": False,
                "mode": "supabase",
                "status_code": exc.code,
                "data": [] if method.upper() == "GET" else None,
                "error": raw,
                "attempt": attempt + 1,
            }
        except Exception as exc:
            last_error = str(exc)
            if attempt >= DB_RETRY_ATTEMPTS:
                return {
                    "success": False,
                    "mode": "supabase_error",
                    "status_code": 0,
                    "data": [] if method.upper() == "GET" else None,
                    "error": last_error,
                    "attempt": attempt + 1,
                }

    return {"success": False, "mode": "supabase_error", "data": [], "error": last_error}

async def db_select(table, query="select=*"):
    if not db_configured():
        return {"success": True, "mode": "memory", "data": MEMORY.get(table, [])}
    return {**supabase_request("GET", f"{table}?{query}"), "table": table}

async def db_insert(table, payload):
    if not db_configured():
        if isinstance(payload, list):
            MEMORY.setdefault(table, []).extend(payload)
        else:
            MEMORY.setdefault(table, []).append(payload)
        return {"success": True, "mode": "memory", "data": payload}
    return {**supabase_request("POST", table, payload=payload), "table": table}

async def db_upsert(table, payload, conflict="id"):
    if not db_configured():
        values = payload if isinstance(payload, list) else [payload]
        items = MEMORY.setdefault(table, [])
        for value in values:
            updated = False
            for i, item in enumerate(items):
                if str(item.get(conflict)) == str(value.get(conflict)):
                    items[i] = {**item, **value}
                    updated = True
                    break
            if not updated:
                items.append(value)
        return {"success": True, "mode": "memory", "data": payload}
    return {**supabase_request("POST", f"{table}?on_conflict={conflict}", payload=payload, prefer="resolution=merge-duplicates,return=representation"), "table": table}

async def log_event(event_type, message, payload=None):
    event = {
        "id": str(uuid.uuid4()),
        "company_id": DEFAULT_COMPANY_ID,
        "event_type": event_type,
        "message": message,
        "payload": payload or {},
        "created_at": datetime.utcnow().isoformat(),
    }
    await db_insert("logs", event)
    return event

def system_state():
    return {
        "version": "enterprise-backend-reviewed-stable",
        "mode": db_mode(),
        "supabase_configured": db_configured(),
        "production_ready": db_configured(),
        "has_supabase_url": bool(SUPABASE_URL),
        "has_supabase_key": bool(SUPABASE_SERVICE_ROLE_KEY),
        "transport": "urllib-defensive",
    }

def price_engine(cost):
    cost = float(cost or 0)
    sale = round((cost + 6 + cost * 0.35) / 0.84, 2)
    return {"cost_price": cost, "sale_price": sale, "profit": round(sale - cost - 6 - sale * 0.16, 2)}

def ai_optimize(product):
    title = f"{product.get('brand','')} {product.get('name','')}".strip()[:60]
    return {"title": title, "description": product.get("description") or title, "seo_score": 100 if len(title) > 20 else 75}

def btn(url, label):
    return f"<a class='btn' href='{url}'>{label}</a>"

def html_shell(title, content):
    return f"""<!doctype html>
<html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{title}</title>
<style>
body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:#f4f7fb;color:#111827}}
aside{{position:fixed;left:0;top:0;bottom:0;width:240px;background:#0b1220;color:white;padding:20px;overflow:auto}}
aside a{{display:block;color:white;text-decoration:none;padding:9px;border-radius:8px;margin:4px 0}}
aside a:hover{{background:#172033}} main{{margin-left:260px;padding:28px}}
.card,.metric{{background:white;border:1px solid #d8dee8;border-radius:14px;padding:18px;margin:14px 0;box-shadow:0 8px 24px rgba(15,23,42,.05)}}
.grid{{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:14px}}
.metric span{{display:block;color:#64748b}} .metric strong{{font-size:24px}}
.btn{{display:inline-block;background:#2563eb;color:white;text-decoration:none;padding:10px 14px;border-radius:10px;margin:6px 5px 6px 0}}
table{{width:100%;border-collapse:collapse;background:white}} th,td{{border-bottom:1px solid #e5e7eb;text-align:left;padding:10px}} th{{background:#f8fafc}}
pre{{background:#0b1220;color:white;padding:14px;border-radius:10px;overflow:auto;white-space:pre-wrap}}
</style></head><body>
<aside><h2>CH</h2><p>CommerceHub<br>Backend Reviewed</p>
<a href='/'>Dashboard</a><a href='/supabase'>Supabase</a><a href='/api/backend/health'>Backend Health</a>
<a href='/products'>Produtos</a><a href='/suppliers'>Fornecedores</a><a href='/inventory'>Estoque</a>
<a href='/mercado-livre'>Mercado Livre</a><a href='/api/health'>API Health</a></aside>
<main><h1>{title}</h1>{content}</main></body></html>"""

@app.get("/", response_class=HTMLResponse)
def dashboard():
    state = system_state()
    content = f"""
<div class='grid'>
<div class='metric'><span>Sistema</span><strong>OK</strong></div>
<div class='metric'><span>Banco</span><strong>{state['mode'].upper()}</strong></div>
<div class='metric'><span>Supabase</span><strong>{state['supabase_configured']}</strong></div>
<div class='metric'><span>Versão</span><strong>Stable</strong></div>
</div>
<div class='card'><h2>CommerceHub Enterprise</h2><p>Backend revisado para falhas controladas e rotas principais sem Internal Server Error.</p>
{btn('/api/health','API Health')}{btn('/api/root-test','Root Test')}{btn('/supabase','Supabase')}{btn('/api/backend/health','Backend Health')}{btn('/products','Produtos')}{btn('/suppliers','Fornecedores')}</div>
"""
    return HTMLResponse(html_shell("Dashboard Enterprise", content))

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_alias():
    return dashboard()

@app.get("/supabase", response_class=HTMLResponse)
def supabase_page():
    test = supabase_request("GET", "companies?select=*&limit=1") if db_configured() else {"success": False, "error": "Supabase não configurado", "data": []}
    content = f"<div class='card'><h2>Diagnóstico Supabase</h2><pre>{json.dumps({'state': system_state(), 'test': test}, ensure_ascii=False, indent=2)}</pre></div>"
    return HTMLResponse(html_shell("Supabase Produção", content), status_code=200)

@app.get("/products", response_class=HTMLResponse)
async def products_page():
    res = await db_select("products", "select=*")
    data = res.get("data") if isinstance(res.get("data"), list) else []
    rows = "".join([f"<tr><td>{p.get('sku','')}</td><td>{p.get('name','')}</td><td>{p.get('brand','')}</td><td>{p.get('stock','')}</td><td>{p.get('sale_price','')}</td></tr>" for p in data])
    if not rows:
        rows = "<tr><td colspan='5'>Nenhum produto cadastrado ainda.</td></tr>"
    content = f"<div class='card'><h2>Produtos</h2><table><tr><th>SKU</th><th>Nome</th><th>Marca</th><th>Estoque</th><th>Preço</th></tr>{rows}</table>{btn('/api/commercial-test/create-product','Criar produto teste')}</div>"
    return HTMLResponse(html_shell("Produtos", content))

@app.get("/suppliers", response_class=HTMLResponse)
async def suppliers_page():
    res = await db_select("suppliers", "select=*")
    data = res.get("data") if isinstance(res.get("data"), list) else []
    rows = "".join([f"<tr><td>{s.get('id','')}</td><td>{s.get('name','')}</td><td>{s.get('type','')}</td><td>{s.get('status','')}</td></tr>" for s in data])
    if not rows:
        rows = "<tr><td colspan='4'>Nenhum fornecedor cadastrado ainda.</td></tr>"
    content = f"<div class='card'><h2>Fornecedores</h2><table><tr><th>ID</th><th>Nome</th><th>Tipo</th><th>Status</th></tr>{rows}</table>{btn('/api/commercial-test/create-product','Criar fornecedor/produto teste')}</div>"
    return HTMLResponse(html_shell("Fornecedores", content))

@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page():
    res = await db_select("inventory", "select=*")
    data = res.get("data") if isinstance(res.get("data"), list) else []
    rows = "".join([f"<tr><td>{i.get('sku','')}</td><td>{i.get('movement_type','')}</td><td>{i.get('quantity','')}</td><td>{i.get('new_stock','')}</td></tr>" for i in data])
    if not rows:
        rows = "<tr><td colspan='4'>Nenhum movimento de estoque cadastrado.</td></tr>"
    content = f"<div class='card'><h2>Estoque</h2><table><tr><th>SKU</th><th>Movimento</th><th>Qtd</th><th>Novo estoque</th></tr>{rows}</table></div>"
    return HTMLResponse(html_shell("Estoque", content))

@app.get("/mercado-livre", response_class=HTMLResponse)
def mercado_livre_page():
    connected = bool(ML_ACCESS_TOKEN and ML_REFRESH_TOKEN)
    auth = "https://auth.mercadolivre.com.br/authorization?" + urlencode({"response_type":"code","client_id":ML_CLIENT_ID,"redirect_uri":ML_REDIRECT_URI}) if ML_CLIENT_ID else ""
    content = f"<div class='card'><h2>Mercado Livre</h2><p>Conectado: <b>{connected}</b></p>{btn('/api/mercadolivre/me','Testar Conta')}{btn('/api/ml/items','Anúncios')}{btn('/api/ml/orders','Pedidos')}</div>"
    return HTMLResponse(html_shell("Mercado Livre", content))

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "commercehub", "version": "enterprise-backend-reviewed-stable"}

@app.get("/api/root-test")
def root_test():
    return {"success": True, "message": "Backend reviewed stable active", **system_state()}

@app.get("/api/foundation/status")
def foundation_status():
    return {"success": True, **system_state(), "tables": list(MEMORY.keys()), "next_test": "/api/backend/health"}

@app.get("/api/supabase/ready")
def supabase_ready():
    test = supabase_request("GET", "companies?select=*&limit=1") if db_configured() else {"success": False, "error": "Supabase não configurado"}
    return {"success": True, **system_state(), "test": test}

@app.get("/api/backend/health")
def backend_health():
    tables = ["companies", "suppliers", "products", "inventory", "orders", "logs"]
    results = {}
    for t in tables:
        r = supabase_request("GET", f"{t}?select=*&limit=1") if db_configured() else {"success": False, "error": "Supabase não configurado", "data": []}
        results[t] = {"success": r.get("success"), "mode": r.get("mode"), "status_code": r.get("status_code"), "rows": len(r.get("data", []) if isinstance(r.get("data"), list) else []), "error": str(r.get("error",""))[:180]}
    return {"success": True, **system_state(), "tables": results}

@app.get("/api/backend/stress-light")
def stress_light():
    checks = []
    started = time.time()
    for i in range(5):
        r = supabase_request("GET", "companies?select=*&limit=1") if db_configured() else {"success": False, "error": "Supabase não configurado"}
        checks.append({"i": i + 1, "success": r.get("success"), "error": str(r.get("error",""))[:120]})
    return {"success": True, "duration_ms": round((time.time() - started)*1000, 2), "checks": checks}

@app.get("/api/db/{table}")
async def api_db(table: str):
    if table not in MEMORY:
        return {"success": False, "message": "Tabela não permitida"}
    return await db_select(table, "select=*")

@app.get("/api/foundation/seed")
@app.post("/api/foundation/seed")
async def seed():
    supplier = {"id": DEFAULT_SUPPLIER_ID, "company_id": DEFAULT_COMPANY_ID, "name": "Fornecedor Manual", "type": "manual", "status": "active", "config": {}}
    product = {"id": DEFAULT_PRODUCT_ID, "company_id": DEFAULT_COMPANY_ID, "supplier_id": DEFAULT_SUPPLIER_ID, "sku": "TESTE-ML-001", "name": "Produto Teste CommerceHub", "brand": "CommerceHub", "category": "Teste", "description": "Produto de teste", "cost_price": 20, "sale_price": price_engine(20)["sale_price"], "stock": 5, "status": "active", "raw_data": {}}
    company = {"id": DEFAULT_COMPANY_ID, "name": "CommerceHub Demo", "document": "00000000000000", "plan": "enterprise", "status": "active"}
    a = await db_upsert("companies", company)
    b = await db_upsert("suppliers", supplier)
    c = await db_upsert("products", product)
    d = await db_insert("inventory", {"id": str(uuid.uuid4()), "company_id": DEFAULT_COMPANY_ID, "product_id": DEFAULT_PRODUCT_ID, "sku": product["sku"], "movement_type": "set", "quantity": 5, "previous_stock": 0, "new_stock": 5, "source": "seed", "created_at": datetime.utcnow().isoformat()})
    await log_event("seed", "Seed executado", {"product": product["sku"]})
    return {"success": True, "mode": db_mode(), "company": a, "supplier": b, "product": c, "inventory": d}

@app.get("/api/commercial-test/create-product")
@app.post("/api/commercial-test/create-product")
async def create_test_product():
    return await seed()

@app.get("/api/commercial-test/check")
async def commercial_check():
    products = await db_select("products", "select=*")
    suppliers = await db_select("suppliers", "select=*")
    inventory = await db_select("inventory", "select=*")
    return {"success": True, "mode": db_mode(), "products": len(products.get("data", [])), "suppliers": len(suppliers.get("data", [])), "inventory": len(inventory.get("data", []))}

@app.get("/api/commercial-test/preview")
async def commercial_preview(category_id: str = "MLBXXXX"):
    product = {"sku": "TESTE-ML-001", "name": "Produto Teste CommerceHub", "brand": "CommerceHub", "description": "Produto de teste", "stock": 5, "cost_price": 20, "sale_price": price_engine(20)["sale_price"]}
    ai = ai_optimize(product)
    return {"success": True, "marketplace": "mercado_livre", "payload": {"title": ai["title"], "category_id": category_id, "price": product["sale_price"], "currency_id": "BRL", "available_quantity": product["stock"], "condition": "new", "description": ai["description"]}}

def ml_request(path, params=None):
    if not ML_ACCESS_TOKEN:
        return {"success": False, "message": "ML_ACCESS_TOKEN ausente"}
    query = ""
    if params:
        query = "?" + urlencode(params)
    req = urllib.request.Request("https://api.mercadolibre.com" + path + query, headers={"Authorization": f"Bearer {ML_ACCESS_TOKEN}"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return {"success": True, "status_code": resp.status, "data": safe_json(resp.read().decode("utf-8"), {})}
    except Exception as exc:
        return {"success": False, "error": str(exc)}

@app.get("/api/mercadolivre/me")
def ml_me():
    return ml_request("/users/me")

@app.get("/api/ml/items")
def ml_items():
    me = ml_request("/users/me")
    user_id = (me.get("data") or {}).get("id") or ML_USER_ID
    if not user_id:
        return {"success": False, "message": "ML_USER_ID ausente"}
    return ml_request(f"/users/{user_id}/items/search", {"limit": 20})

@app.get("/api/ml/orders")
def ml_orders():
    me = ml_request("/users/me")
    user_id = (me.get("data") or {}).get("id") or ML_USER_ID
    if not user_id:
        return {"success": False, "message": "ML_USER_ID ausente"}
    return ml_request("/orders/search", {"seller": user_id, "limit": 20})

@app.post("/api/webhooks/mercadolivre")
async def webhook_ml(request: Request):
    payload = await request.json()
    await db_insert("webhooks", {"id": str(uuid.uuid4()), "company_id": DEFAULT_COMPANY_ID, "marketplace": "mercado_livre", "event_type": payload.get("topic") or "unknown", "payload": payload, "status": "received", "created_at": datetime.utcnow().isoformat()})
    await log_event("webhook_ml", "Webhook recebido", payload)
    return {"success": True, "received": payload}

@app.get("/favicon.ico")
def favicon_ico():
    return {"ok": True}

@app.get("/favicon.png")
def favicon_png():
    return {"ok": True}
