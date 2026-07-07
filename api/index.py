from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from datetime import datetime
import uuid

from core.ui import layout
from core import config
from modules.products.service import all_products, stock_status
from modules.suppliers.service import supplier_products
from modules.listings.service import listing_payload
from modules.ai.service import enrich, optimize_listing
from modules.ai import repository as ai_repo
from modules.marketplace_ops import service as marketplace_ops
from modules.marketplace_ops import repository as marketplace_ops_repo
from modules.universal_connector import service as universal_connector
from modules.import_engine import service as import_engine
from modules.import_engine import repository as import_repo
from modules.sync_engine import service as sync_engine
from modules.scheduler import service as scheduler
from modules.audit import service as audit
from modules.enterprise_dashboard import service as enterprise_dashboard
from modules.mercadolivre import service as ml
from modules.auth import service as auth
from modules.database import service as database

app = FastAPI(title="CommerceHub Sprint 2 Supplier Import Persistent", version="v2-enterprise-base")


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
<p><b>Banco:</b> {database.status()["mode"]}</p><p><b>Versão:</b> CommerceHub Sprint 2 Supplier Import Persistent</p></section>
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






@app.get("/produtos/novo", response_class=HTMLResponse)
def page_product_new():
    body = """
<section class="panel">
<h2>Novo Produto</h2>
<p>Use a API abaixo para cadastrar produto real no Supabase.</p>
<pre>POST /api/products-db</pre>
<h3>Exemplo JSON</h3>
<pre>{
  "sku": "SKU-001",
  "name": "Produto Teste",
  "brand": "Marca",
  "ean": "7890000000000",
  "category": "Categoria",
  "description": "Descrição do produto",
  "cost_price": 20.00,
  "sale_price": 49.90,
  "stock": 10
}</pre>
</section>
"""
    return layout("Novo Produto", body)


@app.get("/product-crud", response_class=HTMLResponse)
def page_product_crud():
    body = """
<section class="panel">
<h2>Product CRUD v1</h2>
<p>Camada de cadastro real de produtos, preparada para Supabase.</p>
<table>
<tr><th>Ação</th><th>Endpoint</th></tr>
<tr><td>Listar</td><td><code>GET /api/products-db</code></td></tr>
<tr><td>Criar</td><td><code>POST /api/products-db</code></td></tr>
<tr><td>Buscar</td><td><code>GET /api/products-db/{id}</code></td></tr>
<tr><td>Editar</td><td><code>PUT /api/products-db/{id}</code></td></tr>
<tr><td>Excluir</td><td><code>DELETE /api/products-db/{id}</code></td></tr>
</table>
</section>
"""
    return layout("Product CRUD", body)




@app.get("/fornecedores/novo", response_class=HTMLResponse)
def page_supplier_new():
    body = """
<section class="panel">
<h2>Novo Fornecedor</h2>
<p>Use a API abaixo para cadastrar fornecedor real no Supabase.</p>
<pre>POST /api/suppliers-db</pre>
<h3>Exemplo JSON</h3>
<pre>{
  "name": "Fornecedor Exemplo",
  "type": "api",
  "status": "active",
  "config": {
    "base_url": "https://api.fornecedor.com.br",
    "auth_type": "token"
  }
}</pre>
</section>
"""
    return layout("Novo Fornecedor", body)


@app.get("/supplier-crud", response_class=HTMLResponse)
def page_supplier_crud():
    body = """
<section class="panel">
<h2>Supplier CRUD v1</h2>
<p>Camada de cadastro real de fornecedores, preparada para Supabase.</p>
<table>
<tr><th>Ação</th><th>Endpoint</th></tr>
<tr><td>Listar</td><td><code>GET /api/suppliers-db</code></td></tr>
<tr><td>Criar</td><td><code>POST /api/suppliers-db</code></td></tr>
<tr><td>Buscar</td><td><code>GET /api/suppliers-db/{id}</code></td></tr>
<tr><td>Editar</td><td><code>PUT /api/suppliers-db/{id}</code></td></tr>
<tr><td>Excluir</td><td><code>DELETE /api/suppliers-db/{id}</code></td></tr>
</table>
</section>
<section class="panel">
<h2>Tipos suportados</h2>
<table>
<tr><th>Tipo</th><th>Status</th><th>Uso</th></tr>
<tr><td>manual</td><td>Ativo</td><td>Cadastro manual</td></tr>
<tr><td>api</td><td>Preparado</td><td>Fornecedor com API REST</td></tr>
<tr><td>xml</td><td>Preparado</td><td>Feed XML</td></tr>
<tr><td>csv</td><td>Preparado</td><td>Planilha/CSV</td></tr>
<tr><td>ftp</td><td>Preparado</td><td>FTP/SFTP</td></tr>
</table>
</section>
"""
    return layout("Supplier CRUD", body)




@app.get("/ml-publish", response_class=HTMLResponse)
def page_ml_publish():
    body = """
<section class="panel">
<h2>Mercado Livre Publish v1</h2>
<p>Camada de publicação real de anúncios no Mercado Livre.</p>
<table>
<tr><th>Ação</th><th>Endpoint</th></tr>
<tr><td>Buscar categorias</td><td><code>GET /api/mercadolivre/categories/search?q=suporte celular</code></td></tr>
<tr><td>Atributos categoria</td><td><code>GET /api/mercadolivre/categories/MLBXXXX/attributes</code></td></tr>
<tr><td>Preview anúncio</td><td><code>GET /api/anuncios/preview/SUP-001?category_id=MLBXXXX</code></td></tr>
<tr><td>Publicar real</td><td><code>POST /api/anuncios/publish-ml/SUP-001?category_id=MLBXXXX</code></td></tr>
<tr><td>Atualizar preço/estoque</td><td><code>PUT /api/mercadolivre/items/MLB123/price-stock</code></td></tr>
<tr><td>Pausar anúncio</td><td><code>PUT /api/mercadolivre/items/MLB123/pause</code></td></tr>
</table>
</section>
<section class="panel">
<h2>Atenção</h2>
<p>A publicação real envia o anúncio para sua conta Mercado Livre conectada. Use primeiro o preview e valide categoria, preço e estoque.</p>
</section>
"""
    return layout("ML Publish", body)




@app.get("/orders-engine", response_class=HTMLResponse)
def page_orders_engine():
    body = """
<section class="panel">
<h2>Orders Engine v1</h2>
<p>Camada de pedidos reais, webhooks e roteamento para fornecedor.</p>
<table>
<tr><th>Ação</th><th>Endpoint</th></tr>
<tr><td>Listar pedidos</td><td><code>GET /api/orders-db</code></td></tr>
<tr><td>Simular pedido</td><td><code>POST /api/pedidos/simulate</code></td></tr>
<tr><td>Ingerir pedido</td><td><code>POST /api/orders/mercado_livre/ingest</code></td></tr>
<tr><td>Webhook ML</td><td><code>POST /api/mercadolivre/webhook</code></td></tr>
<tr><td>Workflow</td><td><code>GET /api/orders/workflow</code></td></tr>
</table>
</section>
"""
    return layout("Orders Engine", body)




@app.get("/inventory-sync", response_class=HTMLResponse)
def page_inventory_sync():
    body = """
<section class="panel">
<h2>Inventory Sync v1</h2>
<p>Camada de estoque e sincronização com marketplace.</p>
<table>
<tr><th>Ação</th><th>Endpoint</th></tr>
<tr><td>Relatório de estoque</td><td><code>GET /api/inventory/report</code></td></tr>
<tr><td>Preview fornecedor</td><td><code>GET /api/inventory/supplier-preview</code></td></tr>
<tr><td>Plano de sincronização</td><td><code>GET /api/inventory/sync-plan</code></td></tr>
<tr><td>Payload Mercado Livre</td><td><code>GET /api/inventory/ml-payload/SUP-001?stock=10</code></td></tr>
<tr><td>Registrar sync</td><td><code>POST /api/inventory/sync-event</code></td></tr>
</table>
</section>
"""
    return layout("Inventory Sync", body)




@app.get("/pricing-automation", response_class=HTMLResponse)
def page_pricing_automation():
    body = """
<section class="panel">
<h2>Pricing Automation v1</h2>
<p>Camada de precificação automática, margem, lucro e payload para Mercado Livre.</p>
<table>
<tr><th>Ação</th><th>Endpoint</th></tr>
<tr><td>Relatório de preços</td><td><code>GET /api/pricing/report</code></td></tr>
<tr><td>Preço por produto</td><td><code>GET /api/pricing/product/SUP-001</code></td></tr>
<tr><td>Simular margem</td><td><code>GET /api/pricing/product/SUP-001?margin_percent=45</code></td></tr>
<tr><td>Payload Mercado Livre</td><td><code>GET /api/pricing/ml-payload/SUP-001</code></td></tr>
<tr><td>Registrar evento</td><td><code>POST /api/pricing/event</code></td></tr>
</table>
</section>
"""
    return layout("Pricing Automation", body)




@app.get("/ai-optimizer", response_class=HTMLResponse)
def page_ai_optimizer():
    body = """
<section class="panel">
<h2>AI Listing Optimizer v1</h2>
<p>Camada de otimização de anúncios com IA: título, descrição, SEO, palavras-chave e busca de categoria.</p>
<table>
<tr><th>Ação</th><th>Endpoint</th></tr>
<tr><td>Otimizar produto</td><td><code>GET /api/ai/optimize/SUP-001</code></td></tr>
<tr><td>Relatório IA</td><td><code>GET /api/ai/report</code></td></tr>
<tr><td>Preview de anúncio otimizado</td><td><code>GET /api/anuncios/preview/SUP-001?category_id=MLBXXXX</code></td></tr>
<tr><td>Registrar evento IA</td><td><code>POST /api/ai/event</code></td></tr>
</table>
</section>
"""
    return layout("AI Listing Optimizer", body)




@app.get("/marketplace-ops", response_class=HTMLResponse)
def page_marketplace_ops():
    body = """
<section class="panel">
<h2>Marketplace Operations v1</h2>
<p>Camada operacional para controlar anúncios, preço, estoque e eventos de marketplace.</p>
<table>
<tr><th>Ação</th><th>Endpoint</th></tr>
<tr><td>Status</td><td><code>GET /api/marketplace-ops/status</code></td></tr>
<tr><td>Plano operacional</td><td><code>GET /api/marketplace-ops/plan</code></td></tr>
<tr><td>Preview operacional</td><td><code>GET /api/marketplace-ops/preview/SUP-001?category_id=MLBXXXX</code></td></tr>
<tr><td>Publicar ML</td><td><code>POST /api/anuncios/publish-ml/SUP-001?category_id=MLBXXXX</code></td></tr>
<tr><td>Atualizar preço/estoque</td><td><code>PUT /api/mercadolivre/items/MLB123/price-stock</code></td></tr>
<tr><td>Pausar anúncio</td><td><code>PUT /api/mercadolivre/items/MLB123/pause</code></td></tr>
<tr><td>Registrar evento</td><td><code>POST /api/marketplace-ops/event</code></td></tr>
</table>
</section>
"""
    return layout("Marketplace Operations", body)




@app.get("/enterprise-final", response_class=HTMLResponse)
def page_enterprise_final():
    summary = enterprise_dashboard.enterprise_summary()
    k = summary["kpis"]
    body = f"""
<section class="grid">
<div class="card"><span>Produtos</span><strong>{k['products']}</strong></div>
<div class="card"><span>Fornecedores</span><strong>{k['suppliers']}</strong></div>
<div class="card"><span>Estoque</span><strong>{k['stock_total']}</strong></div>
<div class="card"><span>Lucro potencial</span><strong>R$ {k['profit_potential']:,.2f}</strong></div>
</section>
<section class="panel">
<h2>Enterprise v1 Final</h2>
<p>Versão consolidada com conectores, importação, sincronização, scheduler, auditoria e dashboard final.</p>
<table>
<tr><th>Módulo</th><th>Status</th></tr>
<tr><td>Universal Supplier Connector</td><td>Ready</td></tr>
<tr><td>Import Engine</td><td>Ready</td></tr>
<tr><td>Sync Engine</td><td>Ready</td></tr>
<tr><td>Scheduler</td><td>Cron-ready</td></tr>
<tr><td>Audit / Logs</td><td>Ready</td></tr>
<tr><td>Dashboard Final</td><td>Ready</td></tr>
</table>
</section>
"""
    return layout("Enterprise Final", body)


@app.get("/universal-connector", response_class=HTMLResponse)
def page_universal_connector():
    body = """
<section class="panel">
<h2>Universal Supplier Connector v1</h2>
<p>Conectores preparados para API, XML, CSV, FTP e Excel.</p>
<pre>/api/connectors/status
/api/connectors/preview</pre>
</section>
"""
    return layout("Universal Connector", body)


@app.get("/sync-engine", response_class=HTMLResponse)
def page_sync_engine():
    body = """
<section class="panel">
<h2>Sync Engine v1</h2>
<p>Motor final de sincronização fornecedor → catálogo → marketplace.</p>
<pre>/api/sync/status
/api/sync/plan
/api/sync/run-demo</pre>
</section>
"""
    return layout("Sync Engine", body)


@app.get("/scheduler", response_class=HTMLResponse)
def page_scheduler():
    body = """
<section class="panel">
<h2>Scheduler v1</h2>
<p>Jobs preparados para sincronização automática usando Vercel Cron ou serviço externo.</p>
<pre>/api/scheduler/status</pre>
</section>
"""
    return layout("Scheduler", body)


@app.get("/audit", response_class=HTMLResponse)
def page_audit():
    body = """
<section class="panel">
<h2>Audit / Logs v1</h2>
<p>Camada final de eventos e auditoria.</p>
<pre>/api/audit/status</pre>
</section>
"""
    return layout("Audit", body)




@app.get("/sprint1", response_class=HTMLResponse)
def page_sprint1():
    body = """
<section class="panel">
<h2>Sprint 1 — Universal Supplier Connector</h2>
<p>Conexão real por API, JSON, XML e CSV.</p>
<table>
<tr><th>Recurso</th><th>Status</th></tr>
<tr><td>API REST Connector</td><td>Ready</td></tr>
<tr><td>JSON Parser</td><td>Ready</td></tr>
<tr><td>CSV Parser</td><td>Ready</td></tr>
<tr><td>XML Parser</td><td>Ready</td></tr>
<tr><td>Import Engine</td><td>Ready</td></tr>
</table>
</section>
<section class="panel"><h2>Endpoints</h2><pre>GET  /api/connectors/status
POST /api/connectors/parse/{source_type}
POST /api/import/from-payload/{source_type}
POST /api/connectors/api-fetch</pre></section>
"""
    return layout("Sprint 1", body)




@app.get("/sprint2", response_class=HTMLResponse)
def page_sprint2():
    body = """
<section class="panel">
<h2>Sprint 2 — Supplier Product Import Persistent</h2>
<p>Importação persistente de produtos de fornecedores para o Supabase.</p>
<table>
<tr><th>Recurso</th><th>Status</th></tr>
<tr><td>Importação JSON/XML/CSV</td><td>Ready</td></tr>
<tr><td>Validação de produtos</td><td>Ready</td></tr>
<tr><td>Separação válidos/inválidos</td><td>Ready</td></tr>
<tr><td>Persistência no Supabase</td><td>Ready</td></tr>
<tr><td>Registro de eventos</td><td>Ready</td></tr>
</table>
</section>
<section class="panel">
<h2>Endpoints</h2>
<pre>
POST /api/import/persist/{source_type}
POST /api/import/event
GET  /api/import/summary/mock
</pre>
</section>
"""
    return layout("Sprint 2", body)


@app.get("/api/database/health")
async def api_database_health():
    return {"success": True, "database": await database.health_check()}




@app.get("/api/suppliers-db/{supplier_id}")
async def api_get_supplier_db(supplier_id: str):
    return await suppliers_repo.get_supplier(supplier_id)


@app.post("/api/suppliers-db")
async def api_create_supplier_db(payload: dict):
    return await suppliers_repo.create_supplier(payload)


@app.put("/api/suppliers-db/{supplier_id}")
async def api_update_supplier_db(supplier_id: str, payload: dict):
    return await suppliers_repo.update_supplier(supplier_id, payload)


@app.delete("/api/suppliers-db/{supplier_id}")
async def api_delete_supplier_db(supplier_id: str):
    return await suppliers_repo.delete_supplier(supplier_id)


@app.get("/api/database/schema")
def api_database_schema():
    return {
        "success": True,
        "tables": [
            "companies",
            "users_app",
            "suppliers",
            "products",
            "listings",
            "orders",
            "events"
        ],
        "message": "Use o arquivo supabase/schema.sql para criar as tabelas no Supabase."
    }


@app.get("/api/products-db")
async def api_products_db():
    return await products_repo.list_products()


@app.post("/api/products-db")
async def api_create_product_db(payload: dict):
    return await products_repo.create_product(payload)




@app.get("/api/products-db/{product_id}")
async def api_get_product_db(product_id: str):
    return await products_repo.get_product(product_id)


@app.put("/api/products-db/{product_id}")
async def api_update_product_db(product_id: str, payload: dict):
    return await products_repo.update_product(product_id, payload)


@app.delete("/api/products-db/{product_id}")
async def api_delete_product_db(product_id: str):
    return await products_repo.delete_product(product_id)


@app.get("/api/suppliers-db")
async def api_suppliers_db():
    return await suppliers_repo.list_suppliers()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "commercehub", "version": "sprint2-supplier-import-persistent-v1"}


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




@app.get("/api/orders-db")
async def api_orders_db():
    return await orders_repo.list_orders()


@app.get("/api/orders/workflow")
def api_orders_workflow():
    return {"success": True, "workflow": workflow()}


@app.post("/api/orders/{marketplace}/ingest")
async def api_orders_ingest(marketplace: str, payload: dict):
    order = normalize_order_from_payload(marketplace, payload)
    saved = await orders_repo.save_order(order)
    routing = route_order_to_supplier(order)
    return {"success": True, "order": order, "saved": saved, "supplier_routing": routing}




@app.get("/api/inventory/report")
def api_inventory_report():
    return inventory.inventory_report()


@app.get("/api/inventory/supplier-preview")
def api_inventory_supplier_preview():
    return inventory.supplier_stock_preview()


@app.get("/api/inventory/sync-plan")
def api_inventory_sync_plan():
    return inventory.sync_plan()


@app.get("/api/inventory/ml-payload/{sku}")
def api_inventory_ml_payload(sku: str, stock: int, marketplace_item_id: str = ""):
    return {"success": True, "payload": inventory.stock_update_payload(sku, stock, marketplace_item_id)}


@app.post("/api/inventory/sync-event")
async def api_inventory_sync_event(payload: dict):
    saved = await inventory_repo.save_inventory_event(payload)
    return {"success": True, "saved": saved, "payload": payload}




@app.get("/api/pricing/report")
def api_pricing_report(margin_percent: float = None):
    return pricing.pricing_report(margin_percent=margin_percent)


@app.get("/api/pricing/product/{sku}")
def api_pricing_product(sku: str, margin_percent: float = None):
    return pricing.product_pricing(sku, margin_percent=margin_percent)


@app.get("/api/pricing/ml-payload/{sku}")
def api_pricing_ml_payload(sku: str, margin_percent: float = None, marketplace_item_id: str = ""):
    return pricing.ml_price_payload(sku, margin_percent=margin_percent, marketplace_item_id=marketplace_item_id)


@app.post("/api/pricing/event")
async def api_pricing_event(payload: dict):
    saved = await pricing_repo.save_pricing_event(payload)
    return {"success": True, "saved": saved, "payload": payload}




@app.get("/api/ai/optimize/{sku}")
def api_ai_optimize(sku: str):
    product = product_by_sku(sku)
    if not product:
        return {"success": False, "message": "Produto não encontrado"}
    return {"success": True, "product": product, "optimized": optimize_listing(product)}


@app.get("/api/ai/report")
def api_ai_report():
    products = all_products()
    return {
        "success": True,
        "count": len(products),
        "products": [
            {
                "sku": p.get("sku"),
                "name": p.get("name"),
                "optimized": optimize_listing(p)
            }
            for p in products
        ]
    }


@app.post("/api/ai/event")
async def api_ai_event(payload: dict):
    saved = await ai_repo.save_ai_event(payload)
    return {"success": True, "saved": saved, "payload": payload}




@app.get("/api/marketplace-ops/status")
def api_marketplace_ops_status():
    return marketplace_ops.status()


@app.get("/api/marketplace-ops/plan")
def api_marketplace_ops_plan():
    return marketplace_ops.operations_plan()


@app.get("/api/marketplace-ops/preview/{sku}")
def api_marketplace_ops_preview(sku: str, category_id: str = "MLBXXXX"):
    return marketplace_ops.listing_operation_preview(sku, category_id)


@app.post("/api/marketplace-ops/event")
async def api_marketplace_ops_event(payload: dict):
    saved = await marketplace_ops_repo.save_operation_event(payload)
    return {"success": True, "saved": saved, "payload": payload}




@app.get("/api/enterprise/summary")
def api_enterprise_summary():
    return enterprise_dashboard.enterprise_summary()


@app.get("/api/connectors/status")
def api_connectors_status():
    return universal_connector.connector_status()


@app.post("/api/connectors/preview")
def api_connectors_preview(payload: dict):
    return universal_connector.preview_connector_payload(payload, payload.get("source_type", "manual"))


@app.get("/api/import/preview")
def api_import_preview():
    return import_engine.import_preview()


@app.get("/api/import/plan")
def api_import_plan():
    return import_engine.import_plan()


@app.get("/api/sync/status")
def api_sync_status():
    return sync_engine.sync_status()


@app.get("/api/sync/plan")
def api_sync_plan():
    return sync_engine.full_sync_plan()


@app.post("/api/sync/run-demo")
def api_sync_run_demo():
    return sync_engine.run_demo_sync()


@app.get("/api/scheduler/status")
def api_scheduler_status():
    return scheduler.scheduler_status()


@app.get("/api/scheduler/job/{job_id}")
def api_scheduler_job(job_id: str):
    return scheduler.job_plan(job_id)


@app.get("/api/audit/status")
def api_audit_status():
    return audit.audit_status()


@app.post("/api/audit/event")
def api_audit_event(payload: dict):
    return {"success": True, "event": audit.build_event(payload.get("event_type", "manual"), payload.get("message", ""), payload)}




@app.post("/api/connectors/parse/{source_type}")
def api_connectors_parse(source_type: str, payload: dict):
    raw_payload = payload.get("payload", payload)
    return universal_connector.parse_payload_by_type(source_type, raw_payload)


@app.post("/api/import/from-payload/{source_type}")
def api_import_from_payload(source_type: str, payload: dict):
    raw_payload = payload.get("payload", payload)
    return import_engine.import_from_payload(source_type, raw_payload)


@app.post("/api/connectors/api-fetch")
async def api_connector_api_fetch(payload: dict):
    return await universal_connector.fetch_api_products(
        url=payload.get("url", ""),
        headers=payload.get("headers", {})
    )




@app.post("/api/import/persist/{source_type}")
async def api_import_persist(source_type: str, payload: dict):
    raw_payload = payload.get("payload", payload)
    parsed = import_engine.import_from_payload(source_type, raw_payload)
    products = parsed.get("valid_products", [])
    persist_result = await import_repo.persist_imported_products(products)
    event_result = await import_repo.save_import_event({
        "source_type": source_type,
        "summary": import_engine.build_import_summary(source_type, products),
        "valid_count": parsed.get("valid_count"),
        "invalid_count": parsed.get("invalid_count")
    })

    return {
        "success": True,
        "parsed": parsed,
        "persist_result": persist_result,
        "event_result": event_result
    }


@app.post("/api/import/event")
async def api_import_event(payload: dict):
    saved = await import_repo.save_import_event(payload)
    return {"success": True, "saved": saved, "payload": payload}


@app.get("/api/import/summary/mock")
def api_import_summary_mock():
    preview = import_engine.import_preview()
    return {
        "success": True,
        "summary": import_engine.build_import_summary("mock_supplier", preview.get("products", [])),
        "preview": preview
    }


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




@app.get("/api/mercadolivre/categories/{category_id}/attributes")
async def api_ml_category_attributes(category_id: str):
    return await ml.category_attributes(category_id)


@app.post("/api/anuncios/publish-ml/{sku}")
async def api_publish_ml(sku: str, category_id: str):
    product = product_by_sku(sku)
    if not product:
        return {"success": False, "message": "Produto não encontrado"}

    ready = readiness(product)
    if not ready.get("ready"):
        return {"success": False, "message": "Produto não está pronto para publicação", "readiness": ready}

    payload = listing_payload(product, category_id)
    result = await ml.publish_item(payload)

    external_id = None
    permalink = None
    if isinstance(result.get("data"), dict):
        external_id = result["data"].get("id")
        permalink = result["data"].get("permalink")

    record = {
        "marketplace": "mercado_livre",
        "external_id": external_id,
        "status": "published" if result.get("success") else "publish_error",
        "payload": payload,
        "permalink": permalink
    }

    save_result = await listings_repo.save_listing(record)

    return {
        "success": result.get("success", False),
        "marketplace_response": result,
        "saved_listing": save_result
    }


@app.put("/api/mercadolivre/items/{item_id}/pause")
async def api_ml_pause_item(item_id: str):
    return await ml.pause_item(item_id)


@app.put("/api/mercadolivre/items/{item_id}/price-stock")
async def api_ml_update_price_stock(item_id: str, payload: dict):
    return await ml.update_item_price_stock(
        item_id=item_id,
        price=payload.get("price"),
        stock=payload.get("stock")
    )


@app.post("/api/mercadolivre/webhook")
async def api_ml_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    event = normalize_ml_webhook(payload)
    saved_event = await orders_repo.save_event(event)

    return {
        "success": True,
        "message": "Webhook recebido",
        "event": event,
        "saved_event": saved_event
    }