from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import settings
from storage import storage
from mock_data import mock_products_with_price
from engines import calculate_price, ai_enrich, stock_status, build_listing_payload, product_profit
from mercadolivre_client import ml_client

app = FastAPI(title="CommerceHub", version=settings.APP_VERSION)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def find_product(sku):
    for p in storage.list_products():
        if p.get("sku") == sku: return p
    for p in mock_products_with_price():
        if p.get("sku") == sku: return p
    return None

def finance_summary():
    products = storage.list_products()
    orders = storage.list_orders()
    return {
        "products_count": len(products),
        "orders_count": len(orders),
        "stock_cost": round(sum(float(p.get("cost_price", 0)) * int(p.get("stock", 0)) for p in products), 2),
        "total_sales": round(sum(float(o.get("total_amount", 0)) for o in orders), 2),
        "products": [product_profit(p) for p in products],
    }

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    products = storage.list_products()
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "page": "Dashboard",
        "produtos": products, "fornecedores": storage.list_suppliers(), "pedidos": storage.list_orders(),
        "estoque_total": sum(int(p.get("stock", 0)) for p in products),
        "custo_total": sum(float(p.get("cost_price", 0)) * int(p.get("stock", 0)) for p in products),
        "ml_status": ml_client.status(),
    })

@app.get("/mercado-livre", response_class=HTMLResponse)
def mercado_livre_page(request: Request):
    return templates.TemplateResponse("mercadolivre.html", {
        "request": request, "page": "Mercado Livre",
        "status": ml_client.status(), "auth_url": ml_client.authorization_url(),
        "webhook_url": f"{settings.APP_URL}/api/mercadolivre/webhook"
    })

@app.get("/fornecedores", response_class=HTMLResponse)
def fornecedores_page(request: Request):
    return templates.TemplateResponse("fornecedores.html", {"request": request, "page": "Fornecedores", "mock_products": mock_products_with_price(), "fornecedores": storage.list_suppliers()})

@app.get("/produtos", response_class=HTMLResponse)
def produtos_page(request: Request):
    return templates.TemplateResponse("produtos.html", {"request": request, "page": "Produtos", "produtos": storage.list_products()})

@app.get("/anuncios", response_class=HTMLResponse)
def anuncios_page(request: Request):
    products = storage.list_products() or mock_products_with_price()
    return templates.TemplateResponse("anuncios.html", {"request": request, "page": "Anúncios", "produtos": products})

@app.get("/pedidos", response_class=HTMLResponse)
def pedidos_page(request: Request):
    return templates.TemplateResponse("pedidos.html", {"request": request, "page": "Pedidos", "pedidos": storage.list_orders()})

@app.get("/relatorios", response_class=HTMLResponse)
def relatorios_page(request: Request):
    return templates.TemplateResponse("relatorios.html", {"request": request, "page": "Relatórios", "financeiro": finance_summary()})

@app.get("/arquitetura", response_class=HTMLResponse)
def arquitetura_page(request: Request):
    return templates.TemplateResponse("arquitetura.html", {"request": request, "page": "Arquitetura"})

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "commercehub-simple", "version": settings.APP_VERSION, "environment": settings.APP_ENV}

@app.get("/api/mercadolivre/status")
def api_ml_status():
    return {"success": True, "status": ml_client.status()}

@app.get("/api/mercadolivre/connect")
def api_ml_connect():
    url = ml_client.authorization_url()
    if not url: return {"success": False, "message": "Credenciais Mercado Livre não configuradas."}
    return RedirectResponse(url)

@app.get("/mercadolivre/callback")
@app.get("/api/mercadolivre/callback")
async def api_ml_callback(code: str = ""):
    result = await ml_client.exchange_code(code)
    return {
        "success": result.get("success"),
        "message": "Copie os tokens para as variáveis da Vercel.",
        "access_token": result.get("data", {}).get("access_token"),
        "refresh_token": result.get("data", {}).get("refresh_token"),
        "expires_in": result.get("data", {}).get("expires_in"),
        "user_id": result.get("data", {}).get("user_id"),
        "raw": result.get("data"),
    }

@app.get("/api/mercadolivre/me")
async def api_ml_me():
    return await ml_client.me()

@app.get("/api/mercadolivre/categories/search")
async def api_ml_categories(q: str):
    return await ml_client.search_categories(q)

@app.post("/api/mercadolivre/webhook")
async def api_ml_webhook(request: Request):
    payload = await request.json()
    return {"success": True, "event": storage.add_event("mercado_livre_webhook", "Webhook recebido.", payload)}

@app.get("/api/fornecedores/mock/products")
def api_mock_products():
    return {"success": True, "products": mock_products_with_price()}

@app.post("/api/fornecedores/mock/import")
def api_import_mock():
    existing = {p.get("sku") for p in storage.list_products()}
    imported = []
    for p in mock_products_with_price():
        if p.get("sku") not in existing:
            imported.append(storage.add_product(p))
    return {"success": True, "imported_count": len(imported), "products": imported}

@app.get("/api/produtos")
def api_products():
    return {"success": True, "products": storage.list_products()}

@app.post("/api/produtos")
def api_create_product(payload: dict):
    if not payload.get("sale_price") and payload.get("cost_price"):
        payload["sale_price"] = calculate_price(payload["cost_price"]).get("sale_price", 0)
    return {"success": True, "product": storage.add_product(payload)}

@app.get("/api/produtos/{sku}/ai")
def api_product_ai(sku: str):
    product = find_product(sku)
    return {"success": bool(product), "product": product, "ai": ai_enrich(product) if product else None}

@app.get("/api/produtos/{sku}/pricing")
def api_product_pricing(sku: str):
    product = find_product(sku)
    return {"success": bool(product), "pricing": calculate_price(product.get("cost_price", 0)) if product else None}

@app.get("/api/anuncios/preview/{sku}")
def api_listing_preview(sku: str, category_id: str = ""):
    product = find_product(sku)
    if not product: return {"success": False, "message": "Produto não encontrado."}
    return {"success": True, "product": product, "payload": build_listing_payload(product, category_id)}

@app.post("/api/anuncios/publish-test/{sku}")
async def api_listing_publish(sku: str, category_id: str):
    product = find_product(sku)
    if not product: return {"success": False, "message": "Produto não encontrado."}
    payload = build_listing_payload(product, category_id)
    return await ml_client.publish(payload)

@app.get("/api/pedidos")
def api_orders():
    return {"success": True, "orders": storage.list_orders()}

@app.post("/api/pedidos/simulate")
def api_order_simulate():
    order = {
        "marketplace": "mercado_livre", "external_order_id": "MLB-ORDER-TEST-001", "status": "paid",
        "total_amount": 89.90, "buyer": {"nickname": "cliente_teste"},
        "items": [{"sku": "SUP-001", "title": "Suporte Veicular Para Celular", "quantity": 1, "unit_price": 89.90}],
        "supplier_action": "send_to_mock_supplier",
    }
    return {"success": True, "order": storage.add_order(order)}

@app.post("/api/pedidos/ingest/{marketplace}")
def api_order_ingest(marketplace: str, payload: dict):
    order = {
        "marketplace": marketplace,
        "external_order_id": str(payload.get("id") or payload.get("order_id") or ""),
        "status": payload.get("status", "received"),
        "total_amount": float(payload.get("total_amount") or 0),
        "items": payload.get("items") or payload.get("order_items") or [],
        "raw": payload,
    }
    return {"success": True, "order": storage.add_order(order)}

@app.get("/api/relatorios/finance")
def api_finance():
    return {"success": True, "finance": finance_summary()}

@app.get("/api/architecture")
def api_architecture():
    return {"success": True, "mode": "simple-working-v1", "files": "menos de 30 arquivos", "modules": ["Mercado Livre", "Fornecedores", "Produtos", "Anúncios", "Pedidos", "Relatórios", "AI", "Pricing", "Inventory"]}
