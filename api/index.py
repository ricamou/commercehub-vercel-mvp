from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import json, uuid, hashlib
from api.core.config import APP_VERSION, DEFAULT_COMPANY_ID
from api.db import store
from api.services.mercadolivre import auth_url, exchange_code, ml_request, get_token
from api.ui.templates import shell, btn

app = FastAPI(title="CommerceHub Enterprise V4", version=APP_VERSION)

def state():
    return {"version": APP_VERSION, "mode": store.mode(), "supabase_configured": store.configured()}

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "commercehub", **state()}

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    token = await get_token()
    content = f"<div class='grid'><div class='metric'><span>Sistema</span><strong>OK</strong></div><div class='metric'><span>Banco</span><strong>{store.mode().upper()}</strong></div><div class='metric'><span>ML</span><strong>{'ON' if token else 'OFF'}</strong></div><div class='metric'><span>Versão</span><strong>V4</strong></div></div><div class='card'><h2>CommerceHub Enterprise V4 - Sprint 1</h2><p>Base limpa: login, empresas, Supabase e OAuth Mercado Livre.</p>{btn('/setup','Setup')}{btn('/login','Login')}{btn('/companies','Empresas')}{btn('/mercado-livre','Mercado Livre')}</div>"
    return HTMLResponse(shell("Dashboard", content))

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_alias():
    return await dashboard()

@app.get("/setup", response_class=HTMLResponse)
def setup():
    content = f"<div class='card'><h2>Setup Sprint 1</h2><pre>{json.dumps(state(), ensure_ascii=False, indent=2)}</pre>{btn('/api/backend/health','Backend Health')}{btn('/api/foundation/seed','Criar empresa inicial')}{btn('/mercado-livre','Mercado Livre')}</div>"
    return HTMLResponse(shell("Setup", content))

@app.get("/api/backend/health")
async def backend_health():
    checks = {}
    for table in ["companies", "users", "oauth_tokens", "logs"]:
        res = await store.select(table, "select=*&limit=1")
        checks[table] = {"success": res.get("success"), "mode": res.get("mode"), "rows": len(res.get("data", [])), "error": str(res.get("error", ""))[:180]}
    return {"success": True, **state(), "checks": checks}

@app.get("/api/foundation/seed")
@app.post("/api/foundation/seed")
async def seed():
    company = {"id": DEFAULT_COMPANY_ID, "name": "CommerceHub Demo", "document": "00000000000000", "plan": "enterprise", "status": "active"}
    user = {"id": str(uuid.uuid4()), "company_id": DEFAULT_COMPANY_ID, "name": "Admin", "email": "admin@commercehub.local", "role": "admin", "password_hash": hashlib.sha256("admin123".encode()).hexdigest(), "status": "active"}
    a = await store.upsert("companies", company)
    b = await store.upsert("users", user, "email")
    return {"success": True, "company": a, "user": b, "login": {"email": "admin@commercehub.local", "password": "admin123"}}

@app.get("/login", response_class=HTMLResponse)
def login_page():
    content = "<div class='card'><h2>Login</h2><form method='post' action='/api/login'><label>Email</label><input name='email' value='admin@commercehub.local'><label>Senha</label><input name='password' value='admin123' type='password'><button type='submit'>Entrar</button></form></div>"
    return HTMLResponse(shell("Login", content))

@app.post("/api/login")
async def login(request: Request):
    form = await request.form()
    email = str(form.get("email") or "")
    password = str(form.get("password") or "")
    users = await store.select("users", f"select=*&email=eq.{email}&limit=1")
    rows = users.get("data") or []
    expected = hashlib.sha256(password.encode()).hexdigest()
    ok = bool(rows and rows[0].get("password_hash") == expected)
    return {"success": ok, "message": "Login OK" if ok else "Login inválido"}

@app.get("/companies", response_class=HTMLResponse)
async def companies_page():
    res = await store.select("companies", "select=*")
    rows = "".join([f"<tr><td>{c.get('id')}</td><td>{c.get('name')}</td><td>{c.get('plan')}</td><td>{c.get('status')}</td></tr>" for c in res.get("data", [])])
    if not rows:
        rows = "<tr><td colspan='4'>Nenhuma empresa cadastrada.</td></tr>"
    return HTMLResponse(shell("Empresas", f"<div class='card'><table><tr><th>ID</th><th>Nome</th><th>Plano</th><th>Status</th></tr>{rows}</table>{btn('/api/foundation/seed','Criar empresa inicial')}</div>"))

@app.get("/mercado-livre", response_class=HTMLResponse)
async def mercado_livre_page():
    token = await get_token()
    content = f"<div class='card'><h2>Mercado Livre</h2><p>Conectado: <b>{bool(token)}</b></p>{btn(auth_url(),'Conectar Mercado Livre')}{btn('/api/mercadolivre/me','Testar conta')}{btn('/api/ml/items','Anúncios')}{btn('/api/ml/orders','Pedidos')}</div>"
    return HTMLResponse(shell("Mercado Livre", content))

@app.get("/mercadolivre/callback", response_class=HTMLResponse)
async def mercado_livre_callback(code: str = ""):
    result = await exchange_code(code)
    return HTMLResponse(shell("Callback Mercado Livre", f"<div class='card'><h2>Resultado OAuth</h2><pre>{json.dumps(result, ensure_ascii=False, indent=2)}</pre>{btn('/mercado-livre','Voltar')}</div>"))

@app.get("/api/mercadolivre/me")
async def ml_me():
    return await ml_request("/users/me")

@app.get("/api/ml/items")
async def ml_items():
    me = await ml_request("/users/me")
    user_id = (me.get("data") or {}).get("id")
    if not user_id:
        return {"success": False, "error": "User ID não encontrado", "me": me}
    return await ml_request(f"/users/{user_id}/items/search", params={"limit": 20})

@app.get("/api/ml/orders")
async def ml_orders():
    me = await ml_request("/users/me")
    user_id = (me.get("data") or {}).get("id")
    if not user_id:
        return {"success": False, "error": "User ID não encontrado", "me": me}
    return await ml_request("/orders/search", params={"seller": user_id, "limit": 20})

@app.get("/api/routes")
def routes():
    return {"success": True, "version": APP_VERSION, "routes": sorted([getattr(r, "path", "") for r in app.routes if getattr(r, "path", "")])}

@app.get("/favicon.ico")
def favicon():
    return {"ok": True}



@app.get("/audit", response_class=HTMLResponse)
async def audit_page():
    content = "<div class='card'><h2>Auditoria Supabase</h2><p>Verifica variáveis, tabelas, REST API, leitura e gravação.</p><a class='btn' href='/api/audit/full'>Executar auditoria completa</a><a class='btn' href='/api/audit/env'>Variáveis</a><a class='btn' href='/api/audit/tables'>Tabelas</a><a class='btn' href='/api/audit/write-test'>Teste gravação</a></div>"
    return HTMLResponse(shell("Auditoria Supabase", content))

@app.get("/api/audit/env")
def audit_env():
    from api.core.config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_ANON_KEY, ML_CLIENT_ID, ML_CLIENT_SECRET, ML_REDIRECT_URI
    def mask(v):
        if not v:
            return {"present": False, "length": 0, "preview": ""}
        return {"present": True, "length": len(v), "preview": v[:8] + "..." + v[-4:]}
    return {"success": True, "version": APP_VERSION, "supabase_url": mask(SUPABASE_URL), "service_role_or_key": mask(SUPABASE_KEY), "anon_key": mask(SUPABASE_ANON_KEY), "ml_client_id": mask(ML_CLIENT_ID), "ml_client_secret": mask(ML_CLIENT_SECRET), "ml_redirect_uri": ML_REDIRECT_URI}

@app.get("/api/audit/tables")
async def audit_tables():
    result = {}
    for table in ["companies", "users", "oauth_tokens", "logs"]:
        res = await store.select(table, "select=*&limit=1")
        result[table] = {"success": bool(res.get("success")), "mode": res.get("mode"), "status_code": res.get("status_code"), "rows": len(res.get("data", []) if isinstance(res.get("data"), list) else []), "error": str(res.get("error", ""))[:300], "raw": str(res.get("raw", ""))[:300]}
    return {"success": True, "version": APP_VERSION, "tables": result}

@app.get("/api/audit/write-test")
async def audit_write_test():
    import uuid
    from datetime import datetime
    payload = {"id": str(uuid.uuid4()), "company_id": DEFAULT_COMPANY_ID, "event_type": "audit_write_test", "message": "Teste de gravação Supabase pelo CommerceHub", "payload": {"source": "audit", "version": APP_VERSION}, "created_at": datetime.utcnow().isoformat()}
    write = await store.upsert("logs", payload, "id")
    read = await store.select("logs", f"select=*&id=eq.{payload['id']}&limit=1")
    ok = bool(write.get("success") and read.get("success") and len(read.get("data", [])) > 0)
    return {"success": ok, "write": {"success": write.get("success"), "mode": write.get("mode"), "status_code": write.get("status_code"), "error": str(write.get("error", ""))[:400], "raw": str(write.get("raw", ""))[:400]}, "read_after_write": {"success": read.get("success"), "rows": len(read.get("data", []) if isinstance(read.get("data"), list) else []), "error": str(read.get("error", ""))[:400]}}

@app.get("/api/audit/full")
async def audit_full():
    env_result = audit_env()
    tables_result = await audit_tables()
    write_result = await audit_write_test()
    backend = await backend_health()
    return {"success": True, "version": APP_VERSION, "summary": {"env_ok": bool(env_result["supabase_url"]["present"] and env_result["service_role_or_key"]["present"]), "write_ok": bool(write_result.get("success")), "mode": store.mode()}, "env": env_result, "backend": backend, "tables": tables_result, "write_test": write_result, "next_action": "Se write_ok=false e aparecer Errno 16, o problema é conectividade/REST Supabase no ambiente Vercel."}
