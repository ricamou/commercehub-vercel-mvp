import os, time, uuid, traceback
from typing import Any, Dict, List
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

APP_VERSION = "enterprise-v6-clean-architecture"
DEFAULT_COMPANY_ID = "00000000-0000-0000-0000-000000000001"
app = FastAPI(title="CommerceHub Enterprise V6", version=APP_VERSION)

def env(name: str, default: str = "") -> str:
    v = os.getenv(name, default)
    if v is None: return ""
    v = str(v).strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1].strip()
    return v

def sb_url(): return (env("SUPABASE_URL") or env("NEXT_PUBLIC_SUPABASE_URL")).rstrip("/")
def sb_service(): return env("SUPABASE_SERVICE_ROLE_KEY") or env("SUPABASE_KEY") or env("SUPABASE_SECRET_KEY")
def sb_public(): return env("SUPABASE_ANON_KEY") or env("NEXT_PUBLIC_SUPABASE_ANON_KEY") or env("SUPABASE_PUBLISHABLE_KEY")
def sb_key(): return sb_service() or sb_public()

def mask(v):
    v = str(v or "").strip()
    return {"present": bool(v), "length": len(v), "preview": (v[:10]+"..."+v[-6:]) if len(v)>20 else (v[:4]+"..." if v else "")}

def headers(prefer="return=representation"):
    k = sb_key()
    return {"apikey": k, "Authorization": f"Bearer {k}", "Accept":"application/json", "Content-Type":"application/json", "Prefer": prefer}

def err(exc, path=""):
    return {"success":False,"version":APP_VERSION,"error_id":str(uuid.uuid4()),"error_type":type(exc).__name__,"message":str(exc),"path":path,"traceback":traceback.format_exc()[-8000:]}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content=err(exc, str(request.url.path)))

def esc(v): return str(v if v is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def money(v):
    try: return f"R$ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except Exception: return "R$ 0,00"

def table(headers_, rows):
    th = "".join(f"<th>{esc(h)}</th>" for h in headers_)
    body = f"<tr><td colspan='{len(headers_)}'>Nenhum registro encontrado.</td></tr>" if not rows else "".join("<tr>"+"".join(f"<td>{esc(c)}</td>" for c in r)+"</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"

def layout(title, content):
    menu=[("Dashboard","/"),("Setup","/setup"),("Database SQL","/database-sql"),("System Check","/system-check"),("Empresas","/companies"),("Usuários","/users"),("Fornecedores","/suppliers"),("Produtos","/products"),("Estoque","/inventory"),("Mercado Livre","/mercado-livre"),("Logs","/logs"),("API Health","/api/health"),("API Routes","/api/routes")]
    links="".join(f"<a href='{u}'>{l}</a>" for l,u in menu)
    return f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{esc(title)} - CommerceHub</title><style>
body{{margin:0;font-family:Arial;background:#f3f6fb;color:#071326}}.sidebar{{position:fixed;left:0;top:0;bottom:0;width:220px;background:#0b1220;color:white;padding:24px 18px;overflow:auto}}.brand{{font-size:26px;font-weight:800;margin-bottom:18px}}.subbrand{{font-size:12px;margin-bottom:24px;line-height:1.2}}.sidebar a{{display:block;color:white;text-decoration:none;padding:9px 6px;border-radius:7px;font-weight:700;font-size:14px}}.sidebar a:hover{{background:#1b2741}}.main{{margin-left:220px;padding:32px}}h1{{margin:0 0 24px;font-size:34px}}.card{{background:white;border:1px solid #d8e0ee;border-radius:12px;padding:22px;margin-bottom:18px;box-shadow:0 8px 20px rgba(15,23,42,.04)}}.btn{{display:inline-block;background:#2563eb;color:white;text-decoration:none;padding:10px 14px;border-radius:8px;font-weight:700;margin:4px 4px 4px 0}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(180px,1fr));gap:14px}}.metric{{background:white;border:1px solid #d8e0ee;border-radius:12px;padding:18px}}.metric small{{color:#52627a;display:block;margin-bottom:8px}}.metric b{{font-size:24px}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:10px 12px;border-bottom:1px solid #d8e0ee;text-align:left;font-size:14px}}th{{background:#f8fafc}}pre{{white-space:pre-wrap;background:#08111f;color:#e5edf7;padding:18px;border-radius:10px;overflow:auto;font-size:13px;max-height:70vh}}@media(max-width:900px){{.sidebar{{position:relative;width:auto}}.main{{margin-left:0}}.grid{{grid-template-columns:1fr}}}}
</style></head><body><aside class='sidebar'><div class='brand'>CH</div><div class='subbrand'>CommerceHub<br>Enterprise V6</div>{links}</aside><main class='main'><h1>{esc(title)}</h1>{content}</main></body></html>"""

async def rest(method, table_name, query="", payload=None, prefer="return=representation"):
    if not sb_url(): return {"success":False,"status_code":0,"table":table_name,"rows":0,"data":[],"raw":"SUPABASE_URL ausente"}
    if not sb_key(): return {"success":False,"status_code":0,"table":table_name,"rows":0,"data":[],"raw":"SUPABASE key ausente"}
    endpoint=f"{sb_url()}/rest/v1/{table_name}" + (("?"+query.lstrip("?")) if query else "")
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        r = await client.request(method, endpoint, headers=headers(prefer), json=payload)
    try: body = r.json()
    except Exception: body = r.text
    return {"success":200<=r.status_code<300,"status_code":r.status_code,"table":table_name,"rows":len(body) if isinstance(body,list) else 0,"data":body if isinstance(body,list) else [],"raw":body if not isinstance(body,list) else ""}

async def select(t, limit=100, order="created_at.desc"): return await rest("GET", t, f"select=*&order={order}&limit={int(limit)}")
async def insert(t, payload): return await rest("POST", t, "", payload)
async def upsert(t, payload, conflict="id"):
    return await rest("POST", t, f"on_conflict={conflict}", payload, "resolution=merge-duplicates,return=representation")

SCHEMA_SQL = r'''
create extension if not exists "uuid-ossp";
create extension if not exists pgcrypto;
create table if not exists public.companies (id uuid primary key default uuid_generate_v4(), name text not null, legal_name text, document text, email text, phone text, plan text not null default 'starter', status text not null default 'active', settings jsonb not null default '{}', created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table if not exists public.users_app (id uuid primary key default uuid_generate_v4(), company_id uuid references public.companies(id) on delete cascade, name text not null, email text not null unique, role text not null default 'admin', password_hash text, status text not null default 'active', created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table if not exists public.suppliers (id uuid primary key default uuid_generate_v4(), company_id uuid references public.companies(id) on delete cascade, name text not null, document text, email text, phone text, type text not null default 'manual', status text not null default 'active', config jsonb not null default '{}', created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table if not exists public.brands (id uuid primary key default uuid_generate_v4(), company_id uuid references public.companies(id) on delete cascade, name text not null, status text not null default 'active', created_at timestamptz not null default now(), updated_at timestamptz not null default now(), unique(company_id, name));
create table if not exists public.categories (id uuid primary key default uuid_generate_v4(), company_id uuid references public.companies(id) on delete cascade, parent_id uuid references public.categories(id) on delete set null, name text not null, marketplace text, external_id text, status text not null default 'active', created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table if not exists public.products (id uuid primary key default uuid_generate_v4(), company_id uuid references public.companies(id) on delete cascade, supplier_id uuid references public.suppliers(id) on delete set null, category_id uuid references public.categories(id) on delete set null, brand_id uuid references public.brands(id) on delete set null, sku text not null, name text not null, brand text, ean text, description text, cost_price numeric(14,2) not null default 0, sale_price numeric(14,2) not null default 0, weight_kg numeric(14,3), height_cm numeric(14,2), width_cm numeric(14,2), length_cm numeric(14,2), status text not null default 'active', raw_data jsonb not null default '{}', created_at timestamptz not null default now(), updated_at timestamptz not null default now(), unique(company_id, sku));
create table if not exists public.inventory (id uuid primary key default uuid_generate_v4(), company_id uuid references public.companies(id) on delete cascade, product_id uuid references public.products(id) on delete cascade, sku text not null, quantity integer not null default 0, reserved integer not null default 0, available integer generated always as (quantity - reserved) stored, status text not null default 'available', created_at timestamptz not null default now(), updated_at timestamptz not null default now(), unique(company_id, product_id));
create table if not exists public.marketplace_accounts (id uuid primary key default uuid_generate_v4(), company_id uuid references public.companies(id) on delete cascade, marketplace text not null, account_name text, external_user_id text, status text not null default 'disconnected', config jsonb not null default '{}', created_at timestamptz not null default now(), updated_at timestamptz not null default now(), unique(company_id, marketplace));
create table if not exists public.oauth_tokens (id text primary key, company_id uuid references public.companies(id) on delete cascade, marketplace text not null, access_token text, refresh_token text, user_id text, expires_in integer, expires_at timestamptz, token_type text not null default 'Bearer', scope text, raw_data jsonb not null default '{}', created_at timestamptz not null default now(), updated_at timestamptz not null default now(), unique(company_id, marketplace));
create table if not exists public.listings (id uuid primary key default uuid_generate_v4(), company_id uuid references public.companies(id) on delete cascade, product_id uuid references public.products(id) on delete cascade, marketplace text not null, external_id text, title text not null, description text, price numeric(14,2) not null default 0, available_quantity integer not null default 0, status text not null default 'draft', permalink text, payload jsonb not null default '{}', published_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table if not exists public.orders (id uuid primary key default uuid_generate_v4(), company_id uuid references public.companies(id) on delete cascade, marketplace text not null, external_order_id text, buyer_name text, buyer_email text, status text not null default 'created', total_amount numeric(14,2) not null default 0, shipping_amount numeric(14,2) not null default 0, paid_at timestamptz, raw_data jsonb not null default '{}', created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table if not exists public.logs (id uuid primary key default uuid_generate_v4(), company_id uuid references public.companies(id) on delete cascade, event_type text not null, level text not null default 'info', message text, payload jsonb not null default '{}', created_at timestamptz not null default now());
create or replace function public.set_updated_at() returns trigger as $$ begin new.updated_at = now(); return new; end; $$ language plpgsql;
do $$ declare t text; begin foreach t in array array['companies','users_app','suppliers','brands','categories','products','inventory','marketplace_accounts','oauth_tokens','listings','orders'] loop execute format('drop trigger if exists trg_%s_updated_at on public.%I', t, t); execute format('create trigger trg_%s_updated_at before update on public.%I for each row execute function public.set_updated_at()', t, t); end loop; end $$;
create index if not exists idx_products_company_sku on public.products(company_id, sku);
create index if not exists idx_inventory_company_sku on public.inventory(company_id, sku);
create index if not exists idx_logs_company_created on public.logs(company_id, created_at desc);
insert into public.companies (id, name, legal_name, document, email, plan, status, settings) values ('00000000-0000-0000-0000-000000000001','CommerceHub Demo','CommerceHub Demo LTDA','00000000000000','admin@commercehub.local','enterprise','active','{"currency":"BRL","timezone":"America/Sao_Paulo"}') on conflict (id) do update set name = excluded.name, updated_at = now();
insert into public.users_app (company_id, name, email, role, password_hash, status) values ('00000000-0000-0000-0000-000000000001','Admin','admin@commercehub.local','admin',encode(digest('admin123','sha256'),'hex'),'active') on conflict (email) do update set name = excluded.name, updated_at = now();
insert into public.suppliers (id, company_id, name, type, status) values ('00000000-0000-0000-0000-000000000101','00000000-0000-0000-0000-000000000001','Fornecedor Manual','manual','active') on conflict (id) do update set name = excluded.name, updated_at = now();
insert into public.brands (id, company_id, name, status) values ('00000000-0000-0000-0000-000000000201','00000000-0000-0000-0000-000000000001','CommerceHub','active') on conflict (id) do update set name = excluded.name, updated_at = now();
insert into public.categories (id, company_id, name, marketplace, status) values ('00000000-0000-0000-0000-000000000301','00000000-0000-0000-0000-000000000001','Acessórios','mercadolivre','active') on conflict (id) do update set name = excluded.name, updated_at = now();
insert into public.products (id, company_id, supplier_id, category_id, brand_id, sku, name, brand, ean, description, cost_price, sale_price, status, raw_data) values ('00000000-0000-0000-0000-000000000401','00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000101','00000000-0000-0000-0000-000000000301','00000000-0000-0000-0000-000000000201','CH-TEST-001','Produto Teste CommerceHub','CommerceHub','7890000000000','Produto inicial do CommerceHub.',25.00,59.90,'active','{"source":"v6_seed"}') on conflict (company_id, sku) do update set name = excluded.name, updated_at = now();
insert into public.inventory (company_id, product_id, sku, quantity, reserved, status) values ('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000401','CH-TEST-001',10,0,'available') on conflict (company_id, product_id) do update set quantity = excluded.quantity, updated_at = now();
insert into public.marketplace_accounts (company_id, marketplace, account_name, status) values ('00000000-0000-0000-0000-000000000001','mercadolivre','Mercado Livre Demo','disconnected') on conflict (company_id, marketplace) do update set account_name = excluded.account_name, updated_at = now();
insert into public.logs (company_id, event_type, level, message, payload) values ('00000000-0000-0000-0000-000000000001','v6_schema','info','CommerceHub V6 schema executado com sucesso','{"version":"enterprise-v6-clean-architecture"}');
select 'commercehub_v6_ready' as status, (select count(*) from public.companies) as companies, (select count(*) from public.products) as products, (select count(*) from public.inventory) as inventory, (select count(*) from public.logs) as logs;
'''

@app.get('/api/health')
async def health(): return {"status":"ok","service":"commercehub","version":APP_VERSION,"mode":"supabase","supabase_configured":bool(sb_url() and sb_key())}
@app.get('/api/routes')
async def routes(): return {"success":True,"version":APP_VERSION,"routes":sorted([r.path for r in app.routes])}

async def system_status():
    tabs=['companies','users_app','suppliers','products','inventory','marketplace_accounts','oauth_tokens','listings','orders','logs']
    counts={}; ok=0; reach=False
    for t in tabs:
        r=await rest('GET',t,'select=*&limit=1000')
        counts[t]={"success":r['success'],"status_code":r['status_code'],"rows":r['rows'],"raw":str(r['raw'])[:300]}
        if r['status_code'] in [200,404]: reach=True
        if r['success']: ok+=1
    return {"success":ok==len(tabs),"version":APP_VERSION,"supabase_reachable":reach,"ok_tables":ok,"total_tables":len(tabs),"counts":counts,"missing_or_error":[t for t,r in counts.items() if not r['success']]}

@app.get('/')
async def dashboard():
    s=await system_status(); c=s.get('counts',{})
    metrics=[('Sistema','OK'),('Versão','V6'),('Supabase','OK' if s.get('supabase_reachable') else 'Pendente'),('Produtos',c.get('products',{}).get('rows',0))]
    grid=''.join(f"<div class='metric'><small>{esc(k)}</small><b>{esc(v)}</b></div>" for k,v in metrics)
    return HTMLResponse(layout('Dashboard Enterprise',f"<div class='grid'>{grid}</div><div class='card'><h2>CommerceHub Enterprise V6</h2><p>Arquitetura limpa, menos de 100 arquivos, FastAPI em api/index.py e Supabase via REST.</p><a class='btn' href='/setup'>Setup</a><a class='btn' href='/system-check'>System Check</a><a class='btn' href='/products'>Produtos</a><a class='btn' href='/mercado-livre'>Mercado Livre</a></div>"))

@app.get('/setup')
async def setup(): return HTMLResponse(layout('Setup',"<div class='card'><h2>Setup V6</h2><p>Valide ambiente, execute schema e popule dados iniciais.</p><a class='btn' href='/api/health'>API Health</a><a class='btn' href='/api/system/status'>Status JSON</a><a class='btn' href='/database-sql'>Copiar SQL</a><a class='btn' href='/api/setup/seed'>Seed via API</a></div><div class='card'><h2>Passo obrigatório</h2><p>Se as tabelas ainda não existem, abra /database-sql, copie o SQL e execute no Supabase > SQL Editor.</p></div>"))
@app.get('/database-sql')
async def database_sql(): return HTMLResponse(layout('Database SQL',f"<div class='card'><h2>SQL do Banco CommerceHub V6</h2><p>Copie tudo e execute no Supabase SQL Editor.</p><pre>{esc(SCHEMA_SQL)}</pre></div>"))
@app.get('/api/system/status')
async def api_system_status(): return await system_status()
@app.get('/system-check')
async def system_check():
    e={"SUPABASE_URL":mask(sb_url()),"SUPABASE_SERVICE_ROLE_KEY":mask(sb_service()),"SUPABASE_ANON_KEY":mask(sb_public()),"ML_CLIENT_ID":mask(env('ML_CLIENT_ID')),"ML_CLIENT_SECRET":mask(env('ML_CLIENT_SECRET')), "ML_REDIRECT_URI":mask(env('ML_REDIRECT_URI'))}
    rows=[[k,v['present'],v['length'],v['preview']] for k,v in e.items()]
    return HTMLResponse(layout('System Check',f"<div class='card'><h2>Ambiente</h2>{table(['Variável','Existe','Tamanho','Preview'],rows)}</div><div class='card'><h2>Schema</h2><pre>{esc(await system_status())}</pre></div>"))

@app.get('/api/setup/seed')
async def seed():
    results={}
    results['company']=await upsert('companies',{"id":DEFAULT_COMPANY_ID,"name":"CommerceHub Demo","legal_name":"CommerceHub Demo LTDA","document":"00000000000000","email":"admin@commercehub.local","plan":"enterprise","status":"active","settings":{"currency":"BRL","timezone":"America/Sao_Paulo"}})
    results['supplier']=await upsert('suppliers',{"id":"00000000-0000-0000-0000-000000000101","company_id":DEFAULT_COMPANY_ID,"name":"Fornecedor Manual","type":"manual","status":"active","config":{"source":"v6_api_seed"}})
    results['brand']=await upsert('brands',{"id":"00000000-0000-0000-0000-000000000201","company_id":DEFAULT_COMPANY_ID,"name":"CommerceHub","status":"active"})
    results['category']=await upsert('categories',{"id":"00000000-0000-0000-0000-000000000301","company_id":DEFAULT_COMPANY_ID,"name":"Acessórios","marketplace":"mercadolivre","status":"active"})
    results['product']=await upsert('products',{"id":"00000000-0000-0000-0000-000000000401","company_id":DEFAULT_COMPANY_ID,"supplier_id":"00000000-0000-0000-0000-000000000101","category_id":"00000000-0000-0000-0000-000000000301","brand_id":"00000000-0000-0000-0000-000000000201","sku":"CH-TEST-001","name":"Produto Teste CommerceHub","brand":"CommerceHub","ean":"7890000000000","description":"Produto inicial criado via API.","cost_price":25.0,"sale_price":59.9,"status":"active","raw_data":{"source":"v6_api_seed"}})
    results['marketplace']=await upsert('marketplace_accounts',{"id":"00000000-0000-0000-0000-000000000501","company_id":DEFAULT_COMPANY_ID,"marketplace":"mercadolivre","account_name":"Mercado Livre Demo","status":"disconnected","config":{"source":"v6_api_seed"}})
    results['log']=await insert('logs',{"company_id":DEFAULT_COMPANY_ID,"event_type":"seed","level":"info","message":"Seed V6 executado pela API","payload":{"version":APP_VERSION}})
    return {"success":True,"version":APP_VERSION,"results":results,"next":"/api/system/status"}

async def rows(t, limit=100):
    r=await select(t, limit); return r['data'] if r['success'] else []
@app.get('/companies')
async def companies_page():
    rs=await rows('companies'); return HTMLResponse(layout('Empresas',f"<div class='card'><h2>Empresas</h2>{table(['Nome','Documento','Email','Plano','Status'],[[r.get('name'),r.get('document'),r.get('email'),r.get('plan'),r.get('status')] for r in rs])}</div>"))
@app.get('/users')
async def users_page():
    rs=await rows('users_app'); return HTMLResponse(layout('Usuários',f"<div class='card'><h2>Usuários</h2>{table(['Nome','Email','Perfil','Status'],[[r.get('name'),r.get('email'),r.get('role'),r.get('status')] for r in rs])}<p>Login inicial planejado: admin@commercehub.local / admin123</p></div>"))
@app.get('/suppliers')
async def suppliers_page():
    rs=await rows('suppliers'); return HTMLResponse(layout('Fornecedores',f"<div class='card'><h2>Fornecedores</h2>{table(['Nome','Tipo','Email','Status'],[[r.get('name'),r.get('type'),r.get('email'),r.get('status')] for r in rs])}</div>"))
@app.get('/products')
async def products_page():
    rs=await rows('products'); html=table(['SKU','Produto','Marca','Custo','Venda','Status'],[[r.get('sku'),r.get('name'),r.get('brand'),money(r.get('cost_price')),money(r.get('sale_price')),r.get('status')] for r in rs]); return HTMLResponse(layout('Produtos',f"<div class='card'><h2>Produtos</h2>{html}<a class='btn' href='/api/products/create-test'>Criar Produto Teste</a></div>"))
@app.get('/api/products/create-test')
async def create_test_product():
    sku=f"CH-AUTO-{int(time.time())}"; product={"company_id":DEFAULT_COMPANY_ID,"sku":sku,"name":f"Produto Automático {sku}","brand":"CommerceHub","description":"Produto criado para validar gravação real.","cost_price":35.50,"sale_price":89.90,"status":"active","raw_data":{"source":"v6_create_test"}}
    created=await insert('products',product); pid=created['data'][0].get('id') if created.get('data') else None; inv=None
    if pid: inv=await insert('inventory',{"company_id":DEFAULT_COMPANY_ID,"product_id":pid,"sku":sku,"quantity":5,"reserved":0,"status":"available"})
    await insert('logs',{"company_id":DEFAULT_COMPANY_ID,"event_type":"product_created","level":"info","message":f"Produto {sku} criado","payload":{"sku":sku,"version":APP_VERSION}})
    return {"success":created['success'],"version":APP_VERSION,"sku":sku,"created":created,"inventory":inv}
@app.get('/inventory')
async def inventory_page():
    rs=await rows('inventory'); return HTMLResponse(layout('Estoque',f"<div class='card'><h2>Estoque</h2>{table(['SKU','Qtd','Reservado','Disponível','Status'],[[r.get('sku'),r.get('quantity'),r.get('reserved'),r.get('available'),r.get('status')] for r in rs])}</div>"))

def ml_data():
    checks={"ML_CLIENT_ID":bool(env('ML_CLIENT_ID')),"ML_CLIENT_SECRET":bool(env('ML_CLIENT_SECRET')), "ML_REDIRECT_URI":bool(env('ML_REDIRECT_URI')), "ML_ACCESS_TOKEN":bool(env('ML_ACCESS_TOKEN')), "ML_REFRESH_TOKEN":bool(env('ML_REFRESH_TOKEN')), "ML_USER_ID":bool(env('ML_USER_ID'))}
    return {"success":True,"version":APP_VERSION,"checks":checks,"oauth_ready":checks['ML_CLIENT_ID'] and checks['ML_CLIENT_SECRET'] and checks['ML_REDIRECT_URI']}
@app.get('/mercado-livre')
async def ml_page():
    m=ml_data(); return HTMLResponse(layout('Mercado Livre',f"<div class='card'><h2>Mercado Livre</h2><p>Preparado para OAuth e sincronização.</p>{table(['Configuração','Status'],[[k,v] for k,v in m['checks'].items()])}<a class='btn' href='/api/ml/readiness'>Readiness JSON</a><a class='btn' href='/api/ml/auth-url'>Gerar URL OAuth</a><a class='btn' href='/api/ml/me'>Testar Conta</a></div>"))
@app.get('/api/ml/readiness')
async def api_ml_readiness(): return ml_data()
@app.get('/api/ml/auth-url')
async def api_ml_auth_url():
    cid=env('ML_CLIENT_ID'); red=env('ML_REDIRECT_URI')
    if not cid or not red: return {"success":False,"error":"Configure ML_CLIENT_ID e ML_REDIRECT_URI na Vercel."}
    return {"success":True,"auth_url":f"https://auth.mercadolivre.com.br/authorization?response_type=code&client_id={cid}&redirect_uri={red}"}
@app.get('/api/ml/me')
async def api_ml_me():
    token=env('ML_ACCESS_TOKEN')
    if not token: return {"success":False,"error":"ML_ACCESS_TOKEN ausente. Faça OAuth primeiro."}
    async with httpx.AsyncClient(timeout=30.0) as client: r=await client.get('https://api.mercadolibre.com/users/me',headers={"Authorization":f"Bearer {token}"})
    try: data=r.json()
    except Exception: data=r.text
    return {"success":200<=r.status_code<300,"status_code":r.status_code,"data":data}
@app.get('/logs')
async def logs_page():
    rs=await rows('logs',50); return HTMLResponse(layout('Logs',f"<div class='card'><h2>Logs</h2>{table(['Data','Tipo','Nível','Mensagem'],[[r.get('created_at'),r.get('event_type'),r.get('level'),r.get('message')] for r in rs])}</div>"))
@app.get('/api/debug/force-error')
async def force_error(): raise RuntimeError('Erro proposital para testar o handler global do CommerceHub V6')
