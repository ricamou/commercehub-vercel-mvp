from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from datetime import datetime
import uuid

from core.ui import layout
from core import config
from modules.products.service import all_products, stock_status
from modules.suppliers.service import supplier_products
from modules.listings.service import listing_payload
from modules.ai.service import enrich
from modules.mercadolivre import service as ml
from modules.auth import service as auth
from modules.database import service as database

app = FastAPI(title="CommerceHub v2 Enterprise Base", version="v2-enterprise-base")


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    ps = all_products()
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
<section class="panel"><h2>Status</h2>
<p><b>Mercado Livre configurado:</b> {bool(config.ML_CLIENT_ID and config.ML_CLIENT_SECRET)}</p>
<p><b>Mercado Livre conectado:</b> {bool(config.ML_ACCESS_TOKEN)}</p>
<p><b>Banco:</b> {database.status()["mode"]}</p><p><b>Versão:</b> CommerceHub v2 Enterprise Base</p></section>
"""
    return layout("Dashboard", body)


@app.get("/mercado-livre", response_class=HTMLResponse)
def page_ml():
    s = ml.status()
    auth = ml.auth_url()
    body = f"""
<section class="panel"><h2>Status Mercado Livre</h2>
<p><b>Client ID:</b> {s['client_id']}</p>
<p><b>Client Secret:</b> {s['client_secret']}</p>
<p><b>Redirect URI:</b> {s['redirect_uri']}</p>
<p><b>Access Token:</b> {s['access_token']}</p>
<p><b>User ID:</b> {s['user_id']}</p>
{f'<a class="btn" href="{auth}">Conectar ao Mercado Livre</a>' if auth else '<p>Configure as credenciais na Vercel.</p>'}
<p><b>Webhook:</b> {config.APP_URL}/api/mercadolivre/webhook</p>
</section>
<section class="panel"><h2>Rotas úteis</h2><pre>/api/mercadolivre/status
/api/mercadolivre/me
/api/mercadolivre/categories/search?q=suporte celular</pre></section>
"""
    return layout("Mercado Livre", body)


@app.get("/fornecedores", response_class=HTMLResponse)
def page_suppliers():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{p['name']}</td><td>R$ {p['cost_price']:.2f}</td><td>R$ {p['sale_price']:.2f}</td><td>{p['stock']}</td></tr>" for p in supplier_products()])
    return layout("Fornecedores", f"<section class='panel'><h2>Fornecedor simulado</h2><table><tr><th>SKU</th><th>Produto</th><th>Custo</th><th>Preço sugerido</th><th>Estoque</th></tr>{rows}</table></section>")


@app.get("/produtos", response_class=HTMLResponse)
def page_products():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{p['name']}</td><td>{p['brand']}</td><td>{stock_status(p['stock'])}</td><td>R$ {p['sale_price']:.2f}</td></tr>" for p in all_products()])
    return layout("Produtos", f"<section class='panel'><h2>Catálogo</h2><table><tr><th>SKU</th><th>Produto</th><th>Marca</th><th>Estoque</th><th>Preço</th></tr>{rows}</table></section>")


@app.get("/anuncios", response_class=HTMLResponse)
def page_listings():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{p['name']}</td><td><code>/api/anuncios/preview/{p['sku']}?category_id=MLBXXXX</code></td></tr>" for p in all_products()])
    return layout("Anúncios", f"<section class='panel'><h2>Preview de anúncios</h2><table><tr><th>SKU</th><th>Produto</th><th>Endpoint</th></tr>{rows}</table></section>")


@app.get("/pedidos", response_class=HTMLResponse)
def page_orders():
    return layout("Pedidos", "<section class='panel'><h2>Pedidos</h2><p>Simular pedido: <code>POST /api/pedidos/simulate</code></p></section>")


@app.get("/relatorios", response_class=HTMLResponse)
def page_reports():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{p['name']}</td><td>R$ {p['profit']:.2f}</td><td>{p['margin_percent']}%</td><td>{p['status']}</td></tr>" for p in all_products()])
    return layout("Relatórios", f"<section class='panel'><h2>Financeiro</h2><table><tr><th>SKU</th><th>Produto</th><th>Lucro</th><th>Margem</th><th>Status</th></tr>{rows}</table></section>")


@app.get("/ai", response_class=HTMLResponse)
def page_ai():
    rows = "".join([f"<tr><td>{p['sku']}</td><td>{p['name']}</td><td>{enrich(p)['title']}</td><td>{enrich(p)['seo_score']}%</td></tr>" for p in all_products()])
    return layout("AI Engine", f"<section class='panel'><h2>Produtos otimizados</h2><table><tr><th>SKU</th><th>Produto</th><th>Título sugerido</th><th>SEO Score</th></tr>{rows}</table></section>")


@app.get("/arquitetura", response_class=HTMLResponse)
def page_architecture():
    body = """
<section class="panel">
<h2>Arquitetura Modular Pro</h2>
<p>Base reorganizada por módulos, mantendo poucos arquivos e deploy simples na Vercel.</p>
<pre>
api/index.py
core/config.py
core/ui.py
modules/
  mercadolivre/service.py
  suppliers/service.py
  products/service.py
  listings/service.py
  ai/service.py
requirements.txt
vercel.json
</pre>
</section>
"""
    return layout("Arquitetura", body)




@app.get("/usuarios", response_class=HTMLResponse)
def page_users():
    rows = "".join([f"<tr><td>{u['id']}</td><td>{u['name']}</td><td>{u['email']}</td><td>{u['role']}</td><td>{u['status']}</td></tr>" for u in auth.users()])
    return layout("Usuários", f"<section class='panel'><h2>Users/Auth</h2><table><tr><th>ID</th><th>Nome</th><th>Email</th><th>Perfil</th><th>Status</th></tr>{rows}</table></section>")


@app.get("/database", response_class=HTMLResponse)
def page_database():
    return layout("Database", f"<section class='panel'><h2>Database</h2><pre>{database.status()}</pre></section>")


@app.get("/api/auth/users")
def api_users():
    return {"success": True, "users": auth.users(), "roles": auth.roles()}


@app.get("/api/database/status")
def api_database_status():
    return {"success": True, "database": database.status()}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "commercehub", "version": "v2-enterprise-base"}


@app.get("/api/produtos")
def api_products():
    return {"success": True, "products": all_products()}


@app.get("/api/fornecedores/mock/products")
def api_supplier_products():
    return {"success": True, "products": supplier_products()}


@app.get("/api/anuncios/preview/{sku}")
def api_listing_preview(sku: str, category_id: str = "MLBXXXX"):
    product = next((p for p in all_products() if p["sku"] == sku), None)
    if not product:
        return {"success": False, "message": "Produto não encontrado"}
    return {"success": True, "product": product, "payload": listing_payload(product, category_id)}


@app.post("/api/pedidos/simulate")
def api_order_simulate():
    return {"success": True, "order": {"id": str(uuid.uuid4()), "external_order_id": "MLB-ORDER-TEST-001", "status": "paid", "created_at": datetime.utcnow().isoformat()}}


@app.get("/api/relatorios/finance")
def api_finance():
    ps = all_products()
    return {"success": True, "products_count": len(ps), "stock_total": sum(p["stock"] for p in ps), "profit_potential": round(sum(p["profit"] * p["stock"] for p in ps), 2), "products": ps}


@app.get("/api/ai/{sku}")
def api_ai(sku: str):
    product = next((p for p in all_products() if p["sku"] == sku), None)
    if not product:
        return {"success": False, "message": "Produto não encontrado"}
    return {"success": True, "product": product, "ai": enrich(product)}


@app.get("/api/mercadolivre/status")
def api_ml_status():
    return {"success": True, "status": ml.status()}


@app.get("/api/mercadolivre/callback")
async def api_ml_callback(code: str = ""):
    if not code:
        return {"success": False, "message": "Código OAuth ausente"}
    return await ml.exchange_code(code)


@app.get("/api/mercadolivre/me")
async def api_ml_me():
    return await ml.me()


@app.get("/api/mercadolivre/categories/search")
async def api_ml_categories(q: str):
    return await ml.categories(q)


@app.post("/api/mercadolivre/webhook")
async def api_ml_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    return {"success": True, "message": "Webhook recebido", "payload": payload}