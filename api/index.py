
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from urllib.parse import urlencode
from datetime import datetime
import os, uuid, hashlib, hmac, time, json

try:
    import httpx
except Exception:
    httpx = None

app = FastAPI(title="CommerceHub Enterprise Supabase Stable Fix", version="enterprise-supabase-stable-fix")


# =========================================================
# CONFIG
# =========================================================

def env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if value is None:
        return ""
    value = str(value).strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()
    return value


APP_URL = env("APP_URL", "https://commercehub-vercel-mvp.vercel.app")
APP_SECRET = env("APP_SECRET", "commercehub-change-me")
SUPABASE_URL = env("SUPABASE_URL") or env("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = env("SUPABASE_SERVICE_ROLE_KEY") or env("SUPABASE_KEY") or env("SUPABASE_ANON_KEY")
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

DEFAULT_COMPANY_ID = env("DEFAULT_COMPANY_ID", "00000000-0000-0000-0000-000000000001")
DEFAULT_USER_ID = env("DEFAULT_USER_ID", "00000000-0000-0000-0000-000000000001")


# =========================================================
# IN-MEMORY FALLBACK
# =========================================================

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

DEMO_COMPANY = {
    "id": DEFAULT_COMPANY_ID,
    "name": "CommerceHub Demo",
    "document": "00000000000000",
    "plan": "enterprise",
    "status": "active",
}

DEMO_USER = {
    "id": DEFAULT_USER_ID,
    "company_id": DEFAULT_COMPANY_ID,
    "name": "Admin CommerceHub",
    "email": "admin@commercehub.local",
    "role": "owner",
    "status": "active",
}

DEMO_SUPPLIERS = [
    {
        "id": "00000000-0000-0000-0000-000000000101",
        "company_id": DEFAULT_COMPANY_ID,
        "name": "Fornecedor Manual",
        "type": "manual",
        "status": "active",
        "config": {},
    }
]

DEMO_PRODUCTS = [
    {
        "id": "00000000-0000-0000-0000-000000001001",
        "company_id": DEFAULT_COMPANY_ID,
        "supplier_id": "00000000-0000-0000-0000-000000000101",
        "sku": "SUP-001",
        "name": "Suporte Veicular Para Celular",
        "brand": "MockAuto",
        "ean": "7890000000011",
        "category": "Acessórios Automotivos",
        "description": "Suporte veicular para celular.",
        "cost_price": 22.90,
        "sale_price": 44.90,
        "stock": 50,
        "status": "active",
        "raw_data": {},
    },
    {
        "id": "00000000-0000-0000-0000-000000001002",
        "company_id": DEFAULT_COMPANY_ID,
        "supplier_id": "00000000-0000-0000-0000-000000000101",
        "sku": "SUP-002",
        "name": "Cabo USB-C Reforçado 1 Metro",
        "brand": "MockTech",
        "ean": "7890000000028",
        "category": "Acessórios para Celular",
        "description": "Cabo USB-C reforçado.",
        "cost_price": 9.90,
        "sale_price": 23.90,
        "stock": 120,
        "status": "active",
        "raw_data": {},
    },
]


# =========================================================
# DB CORE
# =========================================================

def db_configured():
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and httpx)


def db_mode():
    return "supabase" if db_configured() else "memory"


def headers(prefer="return=representation"):
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


async def db_select(table: str, query: str = "select=*"):
    if not db_configured():
        return {"success": True, "mode": "memory", "data": MEMORY.get(table, [])}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{SUPABASE_URL}/rest/v1/{table}?{query}", headers=headers())

        return {
            "success": r.status_code < 400,
            "mode": "supabase",
            "status_code": r.status_code,
            "data": r.json() if r.content and r.status_code < 500 else [],
            "error": r.text if r.status_code >= 400 else "",
        }
    except Exception as exc:
        return {
            "success": False,
            "mode": "supabase_error",
            "status_code": 0,
            "data": [],
            "error": str(exc),
            "table": table,
            "query": query,
            "message": "Falha temporária ao conectar no Supabase. A aplicação não vai mais cair com erro 500."
        }


async def db_insert(table: str, payload):
    if not db_configured():
        if isinstance(payload, list):
            MEMORY.setdefault(table, []).extend(payload)
        else:
            MEMORY.setdefault(table, []).append(payload)
        return {"success": True, "mode": "memory", "data": payload}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=headers(), json=payload)

        return {
            "success": r.status_code < 400,
            "mode": "supabase",
            "status_code": r.status_code,
            "data": r.json() if r.content and r.status_code < 500 else None,
            "error": r.text if r.status_code >= 400 else "",
        }
    except Exception as exc:
        return {
            "success": False,
            "mode": "supabase_error",
            "status_code": 0,
            "data": None,
            "error": str(exc),
            "table": table,
            "message": "db_insert_error"
        }

async def db_upsert(table: str, payload, conflict: str = "id"):
    if not db_configured():
        items = MEMORY.setdefault(table, [])
        values = payload if isinstance(payload, list) else [payload]
        for value in values:
            found = False
            for i, existing in enumerate(items):
                if str(existing.get(conflict)) == str(value.get(conflict)):
                    items[i] = {**existing, **value}
                    found = True
                    break
            if not found:
                items.append(value)
        return {"success": True, "mode": "memory", "data": payload}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={conflict}",
                headers=headers("resolution=merge-duplicates,return=representation"),
                json=payload,
            )

        return {
            "success": r.status_code < 400,
            "mode": "supabase",
            "status_code": r.status_code,
            "data": r.json() if r.content and r.status_code < 500 else None,
            "error": r.text if r.status_code >= 400 else "",
        }
    except Exception as exc:
        return {
            "success": False,
            "mode": "supabase_error",
            "status_code": 0,
            "data": None,
            "error": str(exc),
            "table": table,
            "message": "db_upsert_error"
        }

async def db_patch(table: str, filters: str, payload: dict):
    if not db_configured():
        return {"success": True, "mode": "memory", "message": "Patch aplicado apenas em Supabase.", "payload": payload}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.patch(f"{SUPABASE_URL}/rest/v1/{table}?{filters}", headers=headers(), json=payload)

    return {
        "success": r.status_code < 400,
        "mode": "supabase",
        "status_code": r.status_code,
        "data": r.json() if r.content else None,
        "error": r.text if r.status_code >= 400 else "",
    }


async def log_event(event_type: str, message: str, payload=None, company_id: str = None):
    event = {
        "id": str(uuid.uuid4()),
        "company_id": company_id or DEFAULT_COMPANY_ID,
        "event_type": event_type,
        "message": message,
        "payload": payload or {},
        "created_at": datetime.utcnow().isoformat(),
    }
    MEMORY["logs"].insert(0, event)
    return await db_insert("logs", event)


# =========================================================
# AUTH
# =========================================================

def make_token(user_id: str, company_id: str):
    exp = int(time.time()) + 86400
    body = f"{user_id}:{company_id}:{exp}"
    sig = hmac.new(APP_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}:{sig}"


def verify_token(token: str):
    try:
        user_id, company_id, exp, sig = token.split(":")
        body = f"{user_id}:{company_id}:{exp}"
        expected = hmac.new(APP_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        if int(exp) < int(time.time()):
            return None
        return {"user_id": user_id, "company_id": company_id}
    except Exception:
        return None


# =========================================================
# BUSINESS CORE
# =========================================================

def price_engine(cost_price, margin_percent=None, commission_percent=None, fixed_cost=None):
    cost_price = float(cost_price or 0)
    margin_percent = float(DEFAULT_MARGIN_PERCENT if margin_percent is None else margin_percent)
    commission_percent = float(ML_COMMISSION_PERCENT if commission_percent is None else commission_percent)
    fixed_cost = float(FIXED_OPERATIONAL_COST if fixed_cost is None else fixed_cost)
    variable_fee = commission_percent / 100
    desired_profit = cost_price * margin_percent / 100
    sale_price = (cost_price + fixed_cost + desired_profit) / max(0.01, 1 - variable_fee)
    rounded = int(sale_price) + 0.90
    if rounded < sale_price:
        rounded += 1
    commission = rounded * variable_fee
    profit = rounded - cost_price - fixed_cost - commission
    real_margin = (profit / rounded * 100) if rounded else 0
    return {
        "cost_price": round(cost_price, 2),
        "sale_price": round(rounded, 2),
        "commission": round(commission, 2),
        "fixed_cost": round(fixed_cost, 2),
        "profit": round(profit, 2),
        "margin_percent": round(real_margin, 2),
        "status": "healthy" if real_margin >= 18 else "attention" if real_margin > 0 else "loss",
    }


def ai_optimize(product):
    title = " ".join(f"{product.get('brand','')} {product.get('name','')} {product.get('category','')}".split())[:60]
    description = "\n".join([
        f"Produto: {product.get('name','')}",
        f"Marca: {product.get('brand','')}",
        f"Categoria: {product.get('category','')}",
        f"EAN: {product.get('ean','')}",
        f"Descrição: {product.get('description','Produto disponível para venda.')}",
        "Produto novo. Revise atributos obrigatórios antes de publicar.",
    ])
    keywords = [w.lower() for w in title.replace("-", " ").split() if len(w) > 2]
    score = 100 if len(title) >= 25 and len(keywords) >= 3 else 75
    return {"title": title, "description": description, "keywords": keywords[:12], "seo_score": score}


def stock_status(stock):
    stock = int(stock or 0)
    if stock <= 0:
        return "out_of_stock"
    if stock <= 5:
        return "low_stock"
    return "available"


def listing_payload(product, marketplace="mercado_livre", category_id="MLBXXXX"):
    pricing = price_engine(product.get("cost_price", 0))
    ai = ai_optimize(product)
    return {
        "marketplace": marketplace,
        "payload": {
            "title": ai["title"],
            "category_id": category_id,
            "price": float(product.get("sale_price") or pricing["sale_price"]),
            "currency_id": "BRL",
            "available_quantity": int(product.get("stock") or 0),
            "buying_mode": "buy_it_now",
            "listing_type_id": "gold_special",
            "condition": "new",
            "seller_custom_field": product.get("sku"),
            "pictures": [{"source": product.get("image_url") or "https://via.placeholder.com/800"}],
            "attributes": [
                {"id": "BRAND", "value_name": product.get("brand") or "Genérico"},
                {"id": "GTIN", "value_name": product.get("ean") or ""},
            ],
            "description": ai["description"],
        },
        "ai": ai,
        "pricing": pricing,
    }


# =========================================================
# MARKETPLACE CORE
# =========================================================

def marketplaces():
    return [
        {"marketplace": "mercado_livre", "status": "active", "connected": bool(ML_ACCESS_TOKEN and ML_REFRESH_TOKEN)},
        {"marketplace": "shopee", "status": "prepared", "connected": False},
        {"marketplace": "amazon", "status": "prepared", "connected": False},
        {"marketplace": "magalu", "status": "prepared", "connected": False},
    ]


async def get_oauth_token(marketplace="mercado_livre", company_id=DEFAULT_COMPANY_ID):
    res = await db_select("oauth_tokens", f"company_id=eq.{company_id}&marketplace=eq.{marketplace}&select=*&limit=1")
    if res.get("success") and res.get("data"):
        t = res["data"][0]
        return {"source": db_mode(), "access_token": t.get("access_token"), "refresh_token": t.get("refresh_token"), "user_id": t.get("user_id")}

    return {
        "source": "env",
        "access_token": ML_ACCESS_TOKEN,
        "refresh_token": ML_REFRESH_TOKEN,
        "user_id": ML_USER_ID,
    }


async def save_oauth_token(data, marketplace="mercado_livre", company_id=DEFAULT_COMPANY_ID):
    token = {
        "id": f"{company_id}-{marketplace}",
        "company_id": company_id,
        "marketplace": marketplace,
        "access_token": data.get("access_token", ""),
        "refresh_token": data.get("refresh_token", ""),
        "user_id": str(data.get("user_id", "")),
        "expires_in": int(data.get("expires_in") or 0),
        "token_type": data.get("token_type", "Bearer"),
        "scope": data.get("scope", ""),
        "updated_at": datetime.utcnow().isoformat(),
    }
    result = await db_upsert("oauth_tokens", token, "id")
    await log_event("oauth_token_saved", "Token OAuth salvo", {"marketplace": marketplace, "user_id": token["user_id"]}, company_id)
    return result


def ml_auth_url():
    if not ML_CLIENT_ID:
        return ""
    return "https://auth.mercadolivre.com.br/authorization?" + urlencode({
        "response_type": "code",
        "client_id": ML_CLIENT_ID,
        "redirect_uri": ML_REDIRECT_URI,
    })


async def ml_exchange_code(code):
    if not httpx:
        return {"success": False, "message": "httpx não instalado"}
    payload = {
        "grant_type": "authorization_code",
        "client_id": ML_CLIENT_ID,
        "client_secret": ML_CLIENT_SECRET,
        "code": code,
        "redirect_uri": ML_REDIRECT_URI,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post("https://api.mercadolibre.com/oauth/token", data=payload)
    data = r.json() if r.content else {}
    if r.status_code < 400:
        await save_oauth_token(data)
    return {"success": r.status_code < 400, "status_code": r.status_code, "data": data}


async def ml_refresh_token():
    token = await get_oauth_token()
    if not token.get("refresh_token"):
        return {"success": False, "message": "Refresh token ausente"}
    payload = {
        "grant_type": "refresh_token",
        "client_id": ML_CLIENT_ID,
        "client_secret": ML_CLIENT_SECRET,
        "refresh_token": token["refresh_token"],
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post("https://api.mercadolibre.com/oauth/token", data=payload)
    data = r.json() if r.content else {}
    save = None
    if r.status_code < 400:
        save = await save_oauth_token(data)
    return {"success": r.status_code < 400, "status_code": r.status_code, "data": data, "save": save}


async def ml_request(method, path, params=None, payload=None):
    token = await get_oauth_token()
    if not token.get("access_token"):
        return {"success": False, "message": "Access token ausente"}
    access = token["access_token"]
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.request(
            method,
            "https://api.mercadolibre.com" + path,
            params=params or {},
            json=payload,
            headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
        )
    if r.status_code == 401:
        refreshed = await ml_refresh_token()
        if not refreshed.get("success"):
            return {"success": False, "status_code": 401, "refresh": refreshed}
        access = refreshed["data"].get("access_token")
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.request(
                method,
                "https://api.mercadolibre.com" + path,
                params=params or {},
                json=payload,
                headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
            )
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
# QUEUE / SYNC / CACHE
# =========================================================

CACHE = {}
QUEUE = []


def cache_set(key, value, ttl=300):
    CACHE[key] = {"value": value, "expires_at": time.time() + ttl}
    return value


def cache_get(key):
    item = CACHE.get(key)
    if not item:
        return None
    if item["expires_at"] < time.time():
        CACHE.pop(key, None)
        return None
    return item["value"]


async def enqueue(job_type, payload, company_id=DEFAULT_COMPANY_ID):
    job = {
        "id": str(uuid.uuid4()),
        "company_id": company_id,
        "job_type": job_type,
        "status": "queued",
        "payload": payload,
        "attempts": 0,
        "created_at": datetime.utcnow().isoformat(),
    }
    QUEUE.append(job)
    await db_insert("queue", job)
    await log_event("queue_created", "Job criado", job, company_id)
    return job


async def create_sync_job(sync_type, payload=None, company_id=DEFAULT_COMPANY_ID):
    job = {
        "id": str(uuid.uuid4()),
        "company_id": company_id,
        "sync_type": sync_type,
        "status": "queued",
        "payload": payload or {},
        "created_at": datetime.utcnow().isoformat(),
    }
    await db_insert("sync_jobs", job)
    await enqueue(sync_type, payload or {}, company_id)
    return job


# =========================================================
# SEED CORE
# =========================================================

async def seed_core():
    company = await db_upsert("companies", DEMO_COMPANY, "id")
    user = await db_upsert("users", DEMO_USER, "id")
    suppliers = await db_upsert("suppliers", DEMO_SUPPLIERS, "id")
    products = await db_upsert("products", DEMO_PRODUCTS, "id")

    inventory_rows = []
    for product in DEMO_PRODUCTS:
        inventory_rows.append({
            "id": str(uuid.uuid4()),
            "company_id": product["company_id"],
            "product_id": product["id"],
            "sku": product["sku"],
            "movement_type": "set",
            "quantity": int(product["stock"]),
            "previous_stock": 0,
            "new_stock": int(product["stock"]),
            "source": "seed",
            "created_at": datetime.utcnow().isoformat(),
        })
    inventory = await db_insert("inventory", inventory_rows)

    if ML_ACCESS_TOKEN or ML_REFRESH_TOKEN:
        token = await save_oauth_token({
            "access_token": ML_ACCESS_TOKEN,
            "refresh_token": ML_REFRESH_TOKEN,
            "user_id": ML_USER_ID,
            "expires_in": int(env("ML_TOKEN_EXPIRES_IN", "21600") or 21600),
            "token_type": "Bearer",
            "scope": "env_seed",
        })
    else:
        token = {"success": False, "message": "Token ML ausente"}

    log = await log_event("seed_core", "Fundação V3 criada", {"mode": db_mode()})

    return {
        "success": True,
        "mode": db_mode(),
        "company": company,
        "user": user,
        "suppliers": suppliers,
        "products": products,
        "inventory": inventory,
        "token": token,
        "log": log,
    }



# =========================================================
# PRODUCTION CORE - NO MOCKS MODE
# =========================================================

def empty_state(message: str, action_url: str = "", action_label: str = ""):
    action = f"<p>{button(action_url, action_label)}</p>" if action_url else ""
    return f"""
<div style='padding:22px;border:1px dashed #cbd5e1;border-radius:14px;background:#f8fafc'>
<p>{message}</p>
{action}
</div>
"""


async def table_data(table: str, fallback=None):
    """
    Production-first rule:
    - If Supabase is configured, use only Supabase data.
    - If Supabase is not configured, show fallback only to keep app testable.
    """
    res = await db_select(table, "select=*&order=created_at.desc")
    if db_configured():
        return res.get("data", [])
    return fallback or []


async def ensure_seed_if_empty():
    """
    Creates the first company/user/supplier/products only when tables are empty.
    Safe to run more than once.
    """
    companies = await db_select("companies", "select=*&limit=1")
    if companies.get("data"):
        return {"success": True, "message": "Banco já possui dados. Seed não executado.", "mode": db_mode()}

    return await seed_core()


def product_row_html(p):
    pricing = price_engine(p.get("cost_price", 0))
    sale = float(p.get("sale_price") or pricing["sale_price"])
    stock = int(p.get("stock") or 0)
    return f"<tr><td>{p.get('sku','')}</td><td>{p.get('name','')}</td><td>{p.get('brand','')}</td><td>{stock}</td><td>{stock_status(stock)}</td><td>R$ {sale:.2f}</td></tr>"


def supplier_row_html(s):
    return f"<tr><td>{s.get('id','')}</td><td>{s.get('name','')}</td><td>{s.get('type','')}</td><td>{s.get('status','')}</td></tr>"


def inventory_row_html(i):
    return f"<tr><td>{i.get('sku','')}</td><td>{i.get('movement_type','')}</td><td>{i.get('quantity','')}</td><td>{i.get('new_stock','')}</td><td>{i.get('source','')}</td></tr>"


async def create_demo_real_product():
    supplier = {
        "id": "00000000-0000-0000-0000-000000000101",
        "company_id": DEFAULT_COMPANY_ID,
        "name": "Fornecedor Manual",
        "type": "manual",
        "status": "active",
        "config": {},
    }
    product = {
        "id": "00000000-0000-0000-0000-000000001001",
        "company_id": DEFAULT_COMPANY_ID,
        "supplier_id": supplier["id"],
        "sku": "TESTE-ML-001",
        "name": "Produto Teste CommerceHub",
        "brand": "CommerceHub",
        "ean": "7890000000011",
        "category": "Teste",
        "description": "Produto criado para teste real controlado do CommerceHub.",
        "cost_price": 20.00,
        "sale_price": price_engine(20)["sale_price"],
        "stock": 5,
        "status": "active",
        "raw_data": {"source": "commercial_test"},
    }
    await db_upsert("companies", DEMO_COMPANY, "id")
    await db_upsert("users", DEMO_USER, "id")
    s = await db_upsert("suppliers", supplier, "id")
    p = await db_upsert("products", product, "id")
    inv = await db_insert("inventory", {
        "id": str(uuid.uuid4()),
        "company_id": DEFAULT_COMPANY_ID,
        "product_id": product["id"],
        "sku": product["sku"],
        "movement_type": "set",
        "quantity": product["stock"],
        "previous_stock": 0,
        "new_stock": product["stock"],
        "source": "commercial_test",
        "created_at": datetime.utcnow().isoformat(),
    })
    await log_event("commercial_test_product_created", "Produto de teste comercial criado", product)
    return {"success": True, "supplier": s, "product": p, "inventory": inv, "product_id": product["id"], "sku": product["sku"]}




# =========================================================
# SUPABASE FINAL FIX / DIAGNOSTICS
# =========================================================

def supabase_env_diagnostics():
    return {
        "SUPABASE_URL": bool(SUPABASE_URL),
        "SUPABASE_SERVICE_ROLE_KEY_or_fallback": bool(SUPABASE_SERVICE_ROLE_KEY),
        "httpx": bool(httpx),
        "configured": db_configured(),
        "mode": db_mode(),
        "required_in_vercel": [
            "SUPABASE_URL",
            "SUPABASE_SERVICE_ROLE_KEY"
        ],
        "accepted_fallback_names": [
            "NEXT_PUBLIC_SUPABASE_URL",
            "SUPABASE_KEY",
            "SUPABASE_ANON_KEY"
        ]
    }


async def supabase_connection_test():
    if not SUPABASE_URL:
        return {"success": False, "error": "SUPABASE_URL ausente na Vercel."}
    if not SUPABASE_SERVICE_ROLE_KEY:
        return {"success": False, "error": "SUPABASE_SERVICE_ROLE_KEY ausente na Vercel."}
    if not httpx:
        return {"success": False, "error": "httpx não instalado."}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{SUPABASE_URL}/rest/v1/",
                headers={
                    "apikey": SUPABASE_SERVICE_ROLE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"
                }
            )
        return {
            "success": r.status_code < 500,
            "status_code": r.status_code,
            "message": "Supabase respondeu. Se status for 401/403, revise a chave. Se for 200/404, conexão existe.",
            "body_preview": r.text[:300]
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}




# =========================================================
# UI
# =========================================================

def button(path, label, target="_blank"):
    return f"<a class='btn' href='{path}' target='{target}'>{label}</a>"


def layout(title, body):
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · CommerceHub V3</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:#f4f7fb;color:#111827}}
aside{{position:fixed;left:0;top:0;bottom:0;width:250px;background:#0b1220;color:white;padding:20px 14px;overflow:auto}}
.logo{{display:flex;gap:10px;align-items:center;margin-bottom:24px}}.logo b{{background:#2563eb;padding:12px;border-radius:10px}}.logo span{{display:block;color:#9ca3af;font-size:12px}}
nav a{{display:block;color:white;text-decoration:none;padding:9px;border-radius:8px;margin:3px 0}}nav a:hover{{background:#172033}}
main{{margin-left:250px;padding:28px}}h1{{font-size:32px;margin:0}}header p{{color:#64748b}}
.grid{{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:16px;margin:22px 0}}.card,.panel{{background:white;border:1px solid #d8dee8;border-radius:16px;box-shadow:0 8px 24px rgba(15,23,42,.05)}}
.card{{padding:20px}}.card span{{display:block;color:#64748b}}.card strong{{font-size:28px;display:block;margin-top:10px}}
.panel{{padding:22px;margin:18px 0}}table{{width:100%;border-collapse:collapse;margin-top:12px}}th,td{{padding:11px;border-bottom:1px solid #e5e7eb;text-align:left}}th{{background:#f8fafc}}
pre{{background:#0b1220;color:white;padding:14px;border-radius:10px;overflow:auto}}code{{background:#eef2ff;padding:3px 6px;border-radius:6px}}.btn{{display:inline-block;background:#2563eb;color:white;text-decoration:none;padding:10px 14px;border-radius:10px;margin:6px 5px 6px 0}}
.ok{{color:#16a34a;font-weight:bold}}.bad{{color:#dc2626;font-weight:bold}}
</style>
</head>
<body>
<aside>
<div class="logo"><b>CH</b><div><strong>CommerceHub</strong><span>Enterprise Supabase Stable Fix</span></div></div>
<nav>
<a href="/">Dashboard</a>
<a href="/foundation">Fundação</a>
<a href="/supabase">Supabase</a>
<a href="/companies">Empresas</a>
<a href="/users">Usuários</a>
<a href="/suppliers">Fornecedores</a>
<a href="/products">Produtos</a>
<a href="/inventory">Estoque</a>
<a href="/marketplaces">Marketplaces</a>
<a href="/mercado-livre">Mercado Livre</a>
<a href="/orders">Pedidos</a>
<a href="/listings">Anúncios</a>
<a href="/ai">IA</a>
<a href="/logs">Logs</a>
<a href="/queue">Filas</a>
<a href="/sync">Sync Jobs</a>
<a href="/webhooks">Webhooks</a>
<a href="/api/health" target="_blank">API Health</a>
</nav>
</aside>
<main>
<header><h1>{title}</h1><p>Supabase → Cadastro único → Marketplaces → Cliente</p></header>
{body}
</main>
</body>
</html>"""


# =========================================================
# PAGES
# =========================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    companies = await db_select("companies", "select=*")
    products = await db_select("products", "select=*")
    suppliers = await db_select("suppliers", "select=*")
    orders = await db_select("orders", "select=*")
    mode_badge = "SUPABASE" if db_configured() else "MEMORY"
    body = f"""
<section class="grid">
<div class="card"><span>Banco</span><strong>{mode_badge}</strong></div>
<div class="card"><span>Empresas</span><strong>{len(companies.get('data', []))}</strong></div>
<div class="card"><span>Produtos</span><strong>{len(products.get('data', []))}</strong></div>
<div class="card"><span>Pedidos</span><strong>{len(orders.get('data', []))}</strong></div>
</section>
<section class="panel"><h2>CommerceHub Enterprise</h2>
<p>Base pronta para operação: Supabase → cadastro único → estoque → marketplaces → pedidos → relatórios.</p><p><b>Observação:</b> se o Supabase oscilar, o sistema agora mostra erro controlado em vez de cair com Internal Server Error.</p>
{button('/api/foundation/status','Status JSON')}{button('/api/setup/ensure-seed','Preparar banco')}{button('/api/commercial-test/create-product','Criar produto de teste')}</section>
"""
    return layout("Dashboard Enterprise", body)



@app.get("/supabase", response_class=HTMLResponse)
async def supabase_page():
    diag = supabase_env_diagnostics()
    test = await supabase_connection_test()
    body = f"""
<section class="panel">
<h2>Supabase Produção</h2>
<p>Modo atual: <b>{db_mode()}</b></p>
<p>Produção pronta: <b>{db_configured()}</b></p>
<table>
<tr><th>Verificação</th><th>Status</th></tr>
<tr><td>SUPABASE_URL</td><td>{diag['SUPABASE_URL']}</td></tr>
<tr><td>SUPABASE_SERVICE_ROLE_KEY</td><td>{diag['SUPABASE_SERVICE_ROLE_KEY_or_fallback']}</td></tr>
<tr><td>httpx</td><td>{diag['httpx']}</td></tr>
<tr><td>Conectado</td><td>{diag['configured']}</td></tr>
</table>
<h3>Teste de conexão</h3>
<pre>{test}</pre>
<p>{button('/api/supabase/ready','Status Supabase')}{button('/api/foundation/seed','Seed')}</p>
</section>
"""
    return layout("Supabase Produção", body)



@app.get("/foundation", response_class=HTMLResponse)
def foundation_page():
    tables = ["companies", "users", "suppliers", "products", "inventory", "orders", "listings", "oauth_tokens", "logs", "ai_history", "queue", "webhooks", "sync_jobs"]
    rows = "".join([f"<tr><td>{t}</td><td><code>/api/db/{t}</code></td></tr>" for t in tables])
    body = f"""
<section class="panel">
<h2>Fundação Supabase Definitiva</h2>
<p>Modo atual: <b>{db_mode()}</b></p>
<table><tr><th>Tabela</th><th>Endpoint</th></tr>{rows}</table>
<p>{button('/api/foundation/status','Status')}{button('/api/foundation/seed','Executar seed')}</p>
</section>
"""
    return layout("Fundação", body)


@app.get("/companies", response_class=HTMLResponse)
async def companies_page():
    res = await db_select("companies", "select=*")
    rows = "".join([f"<tr><td>{c.get('id')}</td><td>{c.get('name')}</td><td>{c.get('plan')}</td><td>{c.get('status')}</td></tr>" for c in res.get("data", [])])
    return layout("Empresas", f"<section class='panel'><h2>Empresas</h2><table><tr><th>ID</th><th>Nome</th><th>Plano</th><th>Status</th></tr>{rows}</table>{button('/api/db/companies','JSON')}</section>")


@app.get("/users", response_class=HTMLResponse)
async def users_page():
    res = await db_select("users", "select=*")
    rows = "".join([f"<tr><td>{u.get('id')}</td><td>{u.get('name')}</td><td>{u.get('email')}</td><td>{u.get('role')}</td></tr>" for u in res.get("data", [])])
    token = make_token(DEFAULT_USER_ID, DEFAULT_COMPANY_ID)
    return layout("Usuários", f"<section class='panel'><h2>Usuários</h2><table><tr><th>ID</th><th>Nome</th><th>Email</th><th>Role</th></tr>{rows}</table><p>Token demo:</p><pre>{token}</pre></section>")


@app.get("/suppliers", response_class=HTMLResponse)
async def suppliers_page():
    data = await table_data("suppliers", [] if db_configured() else DEMO_SUPPLIERS)
    if not data:
        body = "<section class='panel'><h2>Fornecedores</h2>" + empty_state("Nenhum fornecedor cadastrado ainda.", "/api/commercial-test/create-product", "Criar fornecedor manual de teste") + "</section>"
        return layout("Fornecedores", body)

    rows = "".join([supplier_row_html(s) for s in data])
    return layout("Fornecedores", f"<section class='panel'><h2>Fornecedores</h2><table><tr><th>ID</th><th>Nome</th><th>Tipo</th><th>Status</th></tr>{rows}</table>{button('/api/db/suppliers','JSON')}{button('/api/commercial-test/create-product','Criar fornecedor/produto teste')}</section>")


@app.get("/products", response_class=HTMLResponse)
async def products_page():
    data = await table_data("products", [] if db_configured() else DEMO_PRODUCTS)
    if not data:
        body = "<section class='panel'><h2>Cadastro único de produtos</h2>" + empty_state("Nenhum produto cadastrado ainda. Crie um produto real ou rode o seed inicial.", "/api/commercial-test/create-product", "Criar produto de teste") + "</section>"
        return layout("Produtos", body)

    rows = "".join([product_row_html(p) for p in data])
    return layout("Produtos", f"<section class='panel'><h2>Cadastro único de produtos</h2><table><tr><th>SKU</th><th>Produto</th><th>Marca</th><th>Estoque</th><th>Status</th><th>Preço</th></tr>{rows}</table>{button('/api/db/products','JSON')}{button('/api/commercial-test/create-product','Criar produto de teste')}</section>")


@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page():
    data = await table_data("inventory", [])
    if not data:
        body = "<section class='panel'><h2>Estoque persistido</h2>" + empty_state("Nenhum movimento de estoque cadastrado ainda.", "/api/commercial-test/create-product", "Criar estoque de teste") + "</section>"
        return layout("Estoque", body)

    rows = "".join([inventory_row_html(i) for i in data])
    return layout("Estoque", f"<section class='panel'><h2>Estoque persistido</h2><table><tr><th>SKU</th><th>Movimento</th><th>Qtd</th><th>Novo estoque</th><th>Origem</th></tr>{rows}</table>{button('/api/db/inventory','JSON')}</section>")


@app.get("/marketplaces", response_class=HTMLResponse)
def marketplaces_page():
    rows = "".join([f"<tr><td>{m['marketplace']}</td><td>{m['status']}</td><td>{m['connected']}</td></tr>" for m in marketplaces()])
    return layout("Marketplaces", f"<section class='panel'><h2>Marketplaces</h2><table><tr><th>Marketplace</th><th>Status</th><th>Conectado</th></tr>{rows}</table>{button('/api/marketplaces','JSON')}</section>")


@app.get("/mercado-livre", response_class=HTMLResponse)
def mercado_livre_page():
    connected = bool(ML_ACCESS_TOKEN and ML_REFRESH_TOKEN)
    auth = ml_auth_url()
    body = f"""
<section class="panel">
<h2>Mercado Livre</h2>
<p class="{'ok' if connected else 'bad'}">{'CONECTADO' if connected else 'NÃO CONECTADO'}</p>
{button(auth, 'Conectar Mercado Livre') if auth and not connected else ''}
{button('/api/mercadolivre/me','Testar Conta')}{button('/api/ml/items','Anúncios')}{button('/api/ml/orders','Pedidos')}
</section>
"""
    return layout("Mercado Livre", body)


@app.get("/orders", response_class=HTMLResponse)
async def orders_page():
    res = await db_select("orders", "select=*")
    rows = "".join([f"<tr><td>{o.get('external_order_id')}</td><td>{o.get('marketplace')}</td><td>{o.get('status')}</td><td>{o.get('total_amount')}</td></tr>" for o in res.get("data", [])])
    return layout("Pedidos", f"<section class='panel'><h2>Pedidos persistidos</h2><table><tr><th>ID externo</th><th>Marketplace</th><th>Status</th><th>Total</th></tr>{rows}</table>{button('/api/db/orders','JSON')}</section>")


@app.get("/listings", response_class=HTMLResponse)
async def listings_page():
    res = await db_select("listings", "select=*")
    rows = "".join([f"<tr><td>{l.get('marketplace')}</td><td>{l.get('external_id')}</td><td>{l.get('status')}</td><td>{l.get('permalink')}</td></tr>" for l in res.get("data", [])])
    return layout("Anúncios", f"<section class='panel'><h2>Anúncios persistidos</h2><table><tr><th>Marketplace</th><th>ID externo</th><th>Status</th><th>Link</th></tr>{rows}</table>{button('/api/db/listings','JSON')}</section>")


@app.get("/ai", response_class=HTMLResponse)
async def ai_page():
    res = await db_select("products", "select=*")
    data = res.get("data") or DEMO_PRODUCTS
    rows = "".join([f"<tr><td>{p.get('sku')}</td><td>{ai_optimize(p)['title']}</td><td>{ai_optimize(p)['seo_score']}%</td><td>R$ {price_engine(p.get('cost_price'))['sale_price']:.2f}</td></tr>" for p in data])
    return layout("IA", f"<section class='panel'><h2>IA — título, descrição, SEO e preço</h2><table><tr><th>SKU</th><th>Título</th><th>SEO</th><th>Preço</th></tr>{rows}</table>{button('/api/ai/report','JSON')}</section>")


@app.get("/logs", response_class=HTMLResponse)
async def logs_page():
    res = await db_select("logs", "select=*&order=created_at.desc")
    rows = "".join([f"<tr><td>{l.get('created_at')}</td><td>{l.get('event_type')}</td><td>{l.get('message')}</td></tr>" for l in res.get("data", [])])
    return layout("Logs", f"<section class='panel'><h2>Logs persistidos</h2><table><tr><th>Data</th><th>Tipo</th><th>Mensagem</th></tr>{rows}</table>{button('/api/db/logs','JSON')}</section>")


@app.get("/queue", response_class=HTMLResponse)
async def queue_page():
    res = await db_select("queue", "select=*&order=created_at.desc")
    rows = "".join([f"<tr><td>{q.get('id')}</td><td>{q.get('job_type')}</td><td>{q.get('status')}</td></tr>" for q in res.get("data", [])])
    return layout("Filas", f"<section class='panel'><h2>Filas persistidas</h2><table><tr><th>ID</th><th>Tipo</th><th>Status</th></tr>{rows}</table>{button('/api/queue/create-demo','Criar job')}</section>")


@app.get("/sync", response_class=HTMLResponse)
async def sync_page():
    res = await db_select("sync_jobs", "select=*&order=created_at.desc")
    rows = "".join([f"<tr><td>{s.get('id')}</td><td>{s.get('sync_type')}</td><td>{s.get('status')}</td></tr>" for s in res.get("data", [])])
    return layout("Sync Jobs", f"<section class='panel'><h2>Sincronização</h2><table><tr><th>ID</th><th>Tipo</th><th>Status</th></tr>{rows}</table>{button('/api/sync/run','Executar sync')}</section>")


@app.get("/webhooks", response_class=HTMLResponse)
def webhooks_page():
    return layout("Webhooks", f"<section class='panel'><h2>Webhooks</h2><pre>{APP_URL}/api/webhooks/mercadolivre</pre>{button('/api/webhooks/status','Status')}</section>")


@app.get("/mercadolivre/callback", response_class=HTMLResponse)
async def ml_callback(code: str = ""):
    if not code:
        return layout("Mercado Livre Callback", "<section class='panel'><h2>Erro</h2><p>Código OAuth ausente.</p></section>")
    result = await ml_exchange_code(code)
    return layout("Mercado Livre conectado", f"<section class='panel'><h2>Resultado</h2><pre>{result}</pre>{button('/api/mercadolivre/me','Testar conta')}</section>")


# =========================================================
# API
# =========================================================


@app.get("/api/supabase/diagnostics")
def api_supabase_diagnostics():
    return {"success": True, **supabase_env_diagnostics()}


@app.get("/api/supabase/test")
async def api_supabase_test():
    return await supabase_connection_test()


@app.get("/api/supabase/ready")
async def api_supabase_ready():
    test = await supabase_connection_test()
    return {
        "success": bool(db_configured() and test.get("success")),
        "mode": db_mode(),
        "production_ready": bool(db_configured() and test.get("success")),
        "diagnostics": supabase_env_diagnostics(),
        "test": test
    }



@app.get("/api/health")
def health():
    return {"status": "ok", "service": "commercehub", "version": "enterprise-supabase-stable-fix"}


@app.get("/api/foundation/status")
def foundation_status():
    return {
        "success": True,
        "version": "enterprise-supabase-stable-fix",
        "mode": db_mode(),
        "supabase_configured": db_configured(),
        "production_ready": db_configured(),
        "diagnostics": supabase_env_diagnostics(),
        "tables": ["companies", "users", "suppliers", "products", "inventory", "orders", "listings", "oauth_tokens", "logs", "ai_history", "queue", "webhooks", "sync_jobs"],
        "flow": "Supabase -> Cadastro único -> Tela -> Mercado Livre/Shopee/Amazon",
        "next_test": "/api/supabase/test"
    }


@app.get("/api/foundation/seed")
@app.post("/api/foundation/seed")
async def foundation_seed():
    return await seed_core()


@app.get("/api/db/{table}")
async def api_db_table(table: str):
    allowed = {"companies", "users", "suppliers", "products", "inventory", "orders", "listings", "oauth_tokens", "logs", "ai_history", "queue", "webhooks", "sync_jobs"}
    if table not in allowed:
        return {"success": False, "message": "Tabela não permitida"}
    res = await db_select(table, "select=*&order=created_at.desc")
    if table == "oauth_tokens" and res.get("data"):
        safe = []
        for row in res["data"]:
            row = dict(row)
            row["access_token"] = bool(row.get("access_token"))
            row["refresh_token"] = bool(row.get("refresh_token"))
            safe.append(row)
        res["data"] = safe
    return res


@app.post("/api/companies")
async def api_company_create(payload: dict):
    payload["id"] = payload.get("id") or str(uuid.uuid4())
    payload["status"] = payload.get("status") or "active"
    return await db_upsert("companies", payload, "id")


@app.post("/api/users")
async def api_user_create(payload: dict):
    payload["id"] = payload.get("id") or str(uuid.uuid4())
    payload["company_id"] = payload.get("company_id") or DEFAULT_COMPANY_ID
    payload["status"] = payload.get("status") or "active"
    return await db_upsert("users", payload, "id")


@app.post("/api/suppliers")
async def api_supplier_create(payload: dict):
    payload["id"] = payload.get("id") or str(uuid.uuid4())
    payload["company_id"] = payload.get("company_id") or DEFAULT_COMPANY_ID
    payload["status"] = payload.get("status") or "active"
    result = await db_upsert("suppliers", payload, "id")
    await log_event("supplier_saved", "Fornecedor salvo", payload, payload["company_id"])
    return result


@app.post("/api/products")
async def api_product_create(payload: dict):
    payload["id"] = payload.get("id") or str(uuid.uuid4())
    payload["company_id"] = payload.get("company_id") or DEFAULT_COMPANY_ID
    payload["status"] = payload.get("status") or "active"
    if not payload.get("sale_price"):
        payload["sale_price"] = price_engine(payload.get("cost_price", 0))["sale_price"]
    result = await db_upsert("products", payload, "id")
    await log_event("product_saved", "Produto salvo", payload, payload["company_id"])
    return result


@app.post("/api/inventory")
async def api_inventory_create(payload: dict):
    payload["id"] = payload.get("id") or str(uuid.uuid4())
    payload["company_id"] = payload.get("company_id") or DEFAULT_COMPANY_ID
    payload["created_at"] = datetime.utcnow().isoformat()
    result = await db_insert("inventory", payload)
    await log_event("inventory_saved", "Movimento de estoque salvo", payload, payload["company_id"])
    return result


@app.post("/api/orders")
async def api_order_create(payload: dict):
    payload["id"] = payload.get("id") or str(uuid.uuid4())
    payload["company_id"] = payload.get("company_id") or DEFAULT_COMPANY_ID
    payload["created_at"] = payload.get("created_at") or datetime.utcnow().isoformat()
    result = await db_upsert("orders", payload, "id")
    await log_event("order_saved", "Pedido salvo", payload, payload["company_id"])
    return result


@app.post("/api/listings")
async def api_listing_create(payload: dict):
    payload["id"] = payload.get("id") or str(uuid.uuid4())
    payload["company_id"] = payload.get("company_id") or DEFAULT_COMPANY_ID
    payload["status"] = payload.get("status") or "draft"
    result = await db_upsert("listings", payload, "id")
    await log_event("listing_saved", "Anúncio salvo", payload, payload["company_id"])
    return result


@app.get("/api/ai/report")
async def api_ai_report():
    products = await db_select("products", "select=*")
    data = products.get("data") or DEMO_PRODUCTS
    output = []
    for product in data:
        ai = ai_optimize(product)
        pricing = price_engine(product.get("cost_price", 0))
        output.append({"sku": product.get("sku"), "product": product.get("name"), "ai": ai, "pricing": pricing})
    await db_insert("ai_history", {"id": str(uuid.uuid4()), "company_id": DEFAULT_COMPANY_ID, "action": "ai_report", "input": {}, "output": output, "created_at": datetime.utcnow().isoformat()})
    return {"success": True, "products": output}


@app.get("/api/marketplaces")
def api_marketplaces():
    return {"success": True, "marketplaces": marketplaces()}


@app.get("/api/mercadolivre/status")
def api_ml_status():
    return {"success": True, "connected": bool(ML_ACCESS_TOKEN and ML_REFRESH_TOKEN), "redirect_uri": ML_REDIRECT_URI, "user_id": ML_USER_ID}


@app.get("/api/mercadolivre/oauth-config")
def api_ml_oauth_config():
    return {"success": True, "auth_url": ml_auth_url(), "redirect_uri": ML_REDIRECT_URI}


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


@app.get("/api/listings/preview/{product_id}")
async def api_listing_preview(product_id: str, marketplace: str = "mercado_livre", category_id: str = "MLBXXXX"):
    product_res = await db_select("products", f"id=eq.{product_id}&select=*&limit=1")
    if not product_res.get("data"):
        product = next((p for p in DEMO_PRODUCTS if p["id"] == product_id or p["sku"] == product_id), None)
    else:
        product = product_res["data"][0]
    if not product:
        return {"success": False, "message": "Produto não encontrado"}
    return {"success": True, **listing_payload(product, marketplace, category_id)}


@app.post("/api/listings/publish-ml/{product_id}")
async def api_listing_publish_ml(product_id: str, category_id: str = "MLBXXXX"):
    preview = await api_listing_preview(product_id, "mercado_livre", category_id)
    if not preview.get("success"):
        return preview
    result = await ml_request("POST", "/items", payload=preview["payload"])
    if result.get("success"):
        listing = {
            "id": str(uuid.uuid4()),
            "company_id": DEFAULT_COMPANY_ID,
            "product_id": product_id,
            "marketplace": "mercado_livre",
            "external_id": result.get("data", {}).get("id"),
            "status": "published",
            "payload": preview["payload"],
            "permalink": result.get("data", {}).get("permalink"),
            "created_at": datetime.utcnow().isoformat(),
        }
        await db_insert("listings", listing)
        await log_event("listing_published", "Anúncio publicado no Mercado Livre", listing)
    return result


@app.get("/api/queue/create-demo")
async def api_queue_demo():
    return await enqueue("sync_inventory", {"source": "manual"})


@app.get("/api/sync/run")
async def api_sync_run():
    job = await create_sync_job("full_sync", {"marketplaces": ["mercado_livre", "shopee", "amazon"]})
    await log_event("sync_started", "Sincronização criada", job)
    return {"success": True, "sync_job": job}


@app.get("/api/webhooks/status")
def api_webhooks_status():
    return {"success": True, "webhooks": [{"marketplace": "mercado_livre", "url": f"{APP_URL}/api/webhooks/mercadolivre"}]}


@app.post("/api/webhooks/mercadolivre")
async def api_webhook_ml(request: Request):
    payload = await request.json()
    webhook = {
        "id": str(uuid.uuid4()),
        "company_id": DEFAULT_COMPANY_ID,
        "marketplace": "mercado_livre",
        "event_type": payload.get("topic") or "unknown",
        "payload": payload,
        "status": "received",
        "created_at": datetime.utcnow().isoformat(),
    }
    await db_insert("webhooks", webhook)
    await log_event("webhook_received", "Webhook Mercado Livre recebido", payload)
    if "orders" in str(payload).lower() or "order" in str(payload).lower():
        await db_insert("orders", {
            "id": str(uuid.uuid4()),
            "company_id": DEFAULT_COMPANY_ID,
            "marketplace": "mercado_livre",
            "external_order_id": str(payload.get("id") or payload.get("resource") or ""),
            "status": "webhook_received",
            "total_amount": 0,
            "payload": payload,
            "created_at": datetime.utcnow().isoformat(),
        })
    return {"success": True, "webhook": webhook}


@app.get("/api/shopee/status")
def shopee_status():
    return {"success": True, "marketplace": "shopee", "status": "prepared", "flow": "Cadastro único -> Shopee"}


@app.get("/api/amazon/status")
def amazon_status():
    return {"success": True, "marketplace": "amazon", "status": "prepared", "flow": "Cadastro único -> Amazon"}


@app.get("/api/magalu/status")
def magalu_status():
    return {"success": True, "marketplace": "magalu", "status": "prepared", "flow": "Cadastro único -> Magalu"}
