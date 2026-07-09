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
    for table in ["companies", "users_app", "oauth_tokens", "logs"]:
        res = await store.select(table, "select=*&limit=1")
        checks[table] = {"success": res.get("success"), "mode": res.get("mode"), "rows": len(res.get("data", [])), "error": str(res.get("error", ""))[:180]}
    return {"success": True, **state(), "checks": checks}

@app.get("/api/foundation/seed")
@app.post("/api/foundation/seed")
async def seed():
    company = {"id": DEFAULT_COMPANY_ID, "name": "CommerceHub Demo", "document": "00000000000000", "plan": "enterprise", "status": "active"}
    user = {"id": str(uuid.uuid4()), "company_id": DEFAULT_COMPANY_ID, "name": "Admin", "email": "admin@commercehub.local", "role": "admin", "password_hash": hashlib.sha256("admin123".encode()).hexdigest(), "status": "active"}
    a = await store.upsert("companies", company)
    b = await store.upsert("users_app", user, "email")
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
    users = await store.select("users_app", f"select=*&email=eq.{email}&limit=1")
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
    content = "<div class='card'><h2>Auditoria Supabase</h2><p>Verifica variáveis, tabelas, REST API, leitura e gravação.</p><a class='btn' href='/api/audit/safe-full'>Executar auditoria segura</a><a class='btn' href='/api/audit/env'>Variáveis</a><a class='btn' href='/api/audit/tables'>Tabelas</a><a class='btn' href='/api/audit/write-test'>Teste gravação</a></div>"
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
    for table in ["companies", "users_app", "oauth_tokens", "logs"]:
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



def _safe_error(exc):
    return {"type": exc.__class__.__name__, "message": str(exc)[:800]}

@app.get("/api/audit/safe-full")
async def audit_safe_full():
    result = {"success": True, "version": APP_VERSION, "steps": {}, "summary": {}}

    try:
        result["steps"]["env"] = audit_env()
    except Exception as exc:
        result["steps"]["env"] = {"success": False, "error": _safe_error(exc)}

    try:
        result["steps"]["tables"] = await audit_tables()
    except Exception as exc:
        result["steps"]["tables"] = {"success": False, "error": _safe_error(exc)}

    try:
        result["steps"]["write_test"] = await audit_write_test()
    except Exception as exc:
        result["steps"]["write_test"] = {"success": False, "error": _safe_error(exc)}

    try:
        result["steps"]["backend_health"] = await backend_health()
    except Exception as exc:
        result["steps"]["backend_health"] = {"success": False, "error": _safe_error(exc)}

    env_data = result["steps"].get("env", {})
    write_data = result["steps"].get("write_test", {})

    result["summary"] = {
        "env_ok": bool(env_data.get("supabase_url", {}).get("present") and env_data.get("service_role_or_key", {}).get("present")),
        "write_ok": bool(write_data.get("success")),
        "mode": store.mode(),
        "supabase_configured": store.configured(),
        "internal_server_error_fixed": True
    }

    if not result["summary"]["write_ok"]:
        result["diagnosis"] = "A aplicação está viva, mas a gravação/leitura no Supabase falhou. Verifique steps.write_test."
    else:
        result["diagnosis"] = "Supabase gravou e leu corretamente."

    return result

@app.get("/audit-safe", response_class=HTMLResponse)
async def audit_safe_page():
    content = "<div class='card'><h2>Auditoria Supabase Segura</h2><p>Esta versão captura cada erro separadamente.</p><a class='btn' href='/api/audit/safe-full'>Executar auditoria segura</a><a class='btn' href='/api/audit/env'>Variáveis</a><a class='btn' href='/api/audit/tables'>Tabelas</a><a class='btn' href='/api/audit/write-test'>Teste gravação</a><a class='btn' href='/api/backend/health'>Backend Health</a></div>"
    return HTMLResponse(shell("Auditoria Segura", content))

@app.get("/api/audit/ping")
def audit_ping():
    return {"success": True, "version": APP_VERSION, "message": "Audit module loaded"}



@app.get("/supabase-test", response_class=HTMLResponse)
async def supabase_test_page():
    content = "<div class='card'><h2>Teste Supabase HTTPX</h2><p>Esta Sprint troca urllib por httpx e testa SELECT, INSERT, UPSERT e DELETE.</p><a class='btn' href='/api/test/supabase'>Teste SELECT</a><a class='btn' href='/api/test/supabase-insert'>Teste INSERT</a><a class='btn' href='/api/test/supabase-crud'>Teste CRUD completo</a><a class='btn' href='/api/audit/safe-full'>Auditoria segura</a></div>"
    return HTMLResponse(shell("Supabase Test", content))

@app.get("/api/test/supabase")
async def test_supabase_minimal():
    try:
        res = await store.select("companies", "select=*&limit=1")
        return {"success": bool(res.get("success")), "version": APP_VERSION, "mode": store.mode(), "supabase_configured": store.configured(), "table": "companies", "operation": "select", "transport": res.get("transport"), "status_code": res.get("status_code"), "rows": len(res.get("data", []) if isinstance(res.get("data"), list) else []), "data": res.get("data"), "error": str(res.get("error", ""))[:600], "raw": str(res.get("raw", ""))[:600]}
    except Exception as exc:
        return {"success": False, "version": APP_VERSION, "exception": exc.__class__.__name__, "error": str(exc)[:800]}

@app.get("/api/test/supabase-insert")
async def test_supabase_insert():
    import uuid
    from datetime import datetime
    item = {"id": str(uuid.uuid4()), "company_id": DEFAULT_COMPANY_ID, "event_type": "supabase_httpx_insert_test", "message": "Teste INSERT via httpx", "payload": {"version": APP_VERSION, "source": "sprint2"}, "created_at": datetime.utcnow().isoformat()}
    try:
        write = await store.insert("logs", item)
        read = await store.select("logs", f"select=*&id=eq.{item['id']}&limit=1")
        return {"success": bool(write.get("success") and read.get("success") and len(read.get("data", [])) > 0), "version": APP_VERSION, "write": {"success": write.get("success"), "transport": write.get("transport"), "status_code": write.get("status_code"), "error": str(write.get("error", ""))[:600], "raw": str(write.get("raw", ""))[:600]}, "read_after_write": {"success": read.get("success"), "rows": len(read.get("data", []) if isinstance(read.get("data"), list) else []), "error": str(read.get("error", ""))[:600]}}
    except Exception as exc:
        return {"success": False, "version": APP_VERSION, "exception": exc.__class__.__name__, "error": str(exc)[:800]}

@app.get("/api/test/supabase-crud")
async def test_supabase_crud():
    import uuid
    from datetime import datetime
    log_id = str(uuid.uuid4())
    payload = {"id": log_id, "company_id": DEFAULT_COMPANY_ID, "event_type": "supabase_httpx_crud_test", "message": "Teste CRUD inicial", "payload": {"step": "create", "version": APP_VERSION}, "created_at": datetime.utcnow().isoformat()}
    create = await store.upsert("logs", payload, "id")
    read1 = await store.select("logs", f"select=*&id=eq.{log_id}&limit=1")
    payload["message"] = "Teste CRUD atualizado"
    payload["payload"] = {"step": "update", "version": APP_VERSION}
    update = await store.upsert("logs", payload, "id")
    read2 = await store.select("logs", f"select=*&id=eq.{log_id}&limit=1")
    delete = await store.delete("logs", f"id=eq.{log_id}")
    read3 = await store.select("logs", f"select=*&id=eq.{log_id}&limit=1")
    return {"success": bool(create.get("success") and read1.get("success") and update.get("success") and read2.get("success") and delete.get("success") and read3.get("success")), "version": APP_VERSION, "transport": "httpx-async", "create": {"success": create.get("success"), "status_code": create.get("status_code"), "error": str(create.get("error", ""))[:400]}, "read_after_create": {"success": read1.get("success"), "rows": len(read1.get("data", []) if isinstance(read1.get("data"), list) else [])}, "update": {"success": update.get("success"), "status_code": update.get("status_code"), "error": str(update.get("error", ""))[:400]}, "read_after_update": {"success": read2.get("success"), "rows": len(read2.get("data", []) if isinstance(read2.get("data"), list) else [])}, "delete": {"success": delete.get("success"), "status_code": delete.get("status_code"), "error": str(delete.get("error", ""))[:400]}, "read_after_delete": {"success": read3.get("success"), "rows": len(read3.get("data", []) if isinstance(read3.get("data"), list) else [])}}




# =========================
# SPRINT 3 - INFRA AUDIT
# =========================

def _mask_value(value):
    if not value:
        return {"present": False, "length": 0, "preview": ""}
    value = str(value)
    if len(value) <= 12:
        preview = value[:3] + "..."
    else:
        preview = value[:12] + "..." + value[-6:]
    return {"present": True, "length": len(value), "preview": preview}

@app.get("/infra-audit", response_class=HTMLResponse)
async def infra_audit_page():
    content = """
<div class='card'>
<h2>Auditoria de Infraestrutura</h2>
<p>Verifica URL, chave, DNS, HTTPS, REST, Auth e Supabase.</p>
<a class='btn' href='/api/infra/env'>Variáveis mascaradas</a>
<a class='btn' href='/api/infra/dns'>DNS</a>
<a class='btn' href='/api/infra/https'>HTTPS</a>
<a class='btn' href='/api/infra/rest-root'>REST Root</a>
<a class='btn' href='/api/infra/auth-root'>Auth Root</a>
<a class='btn' href='/api/infra/full'>Auditoria completa</a>
</div>
"""
    return HTMLResponse(shell("Infra Audit", content))

@app.get("/api/infra/env")
def infra_env():
    from api.core.config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_ANON_KEY, ML_CLIENT_ID, ML_CLIENT_SECRET, ML_REDIRECT_URI
    url = str(SUPABASE_URL or "").strip()
    return {
        "success": True,
        "version": APP_VERSION,
        "supabase_url": _mask_value(url),
        "supabase_url_checks": {
            "starts_with_https": url.startswith("https://"),
            "ends_with_supabase_co": url.endswith(".supabase.co"),
            "contains_spaces": (" " in url),
            "contains_line_break": ("\n" in url or "\r" in url),
        },
        "service_role_or_key": _mask_value(SUPABASE_KEY),
        "anon_key": _mask_value(SUPABASE_ANON_KEY),
        "ml_client_id": _mask_value(ML_CLIENT_ID),
        "ml_client_secret": _mask_value(ML_CLIENT_SECRET),
        "ml_redirect_uri": ML_REDIRECT_URI,
        "note": "Chaves e URL estão mascaradas por segurança."
    }

@app.get("/api/infra/dns")
def infra_dns():
    from api.core.config import SUPABASE_URL
    import socket
    from urllib.parse import urlparse

    url = str(SUPABASE_URL or "").strip()
    host = urlparse(url).hostname if url else ""
    if not host:
        return {"success": False, "version": APP_VERSION, "error": "SUPABASE_URL sem hostname válido", "url": _mask_value(url)}

    try:
        infos = socket.getaddrinfo(host, 443)
        addresses = sorted(list(set([i[4][0] for i in infos])))
        return {"success": True, "version": APP_VERSION, "host": host, "addresses": addresses[:10], "count": len(addresses)}
    except Exception as exc:
        return {"success": False, "version": APP_VERSION, "host": host, "error_type": exc.__class__.__name__, "error": str(exc)}

@app.get("/api/infra/https")
async def infra_https():
    from api.core.config import SUPABASE_URL
    from api.core.http_client import async_request_json
    url = str(SUPABASE_URL or "").strip().rstrip("/")
    if not url:
        return {"success": False, "version": APP_VERSION, "error": "SUPABASE_URL ausente"}

    result = await async_request_json("GET", url, {}, None, 15)
    return {
        "success": result.get("status_code") is not None and result.get("status_code") != 0,
        "version": APP_VERSION,
        "target": _mask_value(url),
        "transport": result.get("transport"),
        "status_code": result.get("status_code"),
        "error": str(result.get("error", ""))[:800],
        "raw": str(result.get("raw", ""))[:800],
    }

@app.get("/api/infra/rest-root")
async def infra_rest_root():
    from api.core.config import SUPABASE_URL, SUPABASE_KEY
    from api.core.http_client import async_request_json
    url = str(SUPABASE_URL or "").strip().rstrip("/")
    if not url:
        return {"success": False, "version": APP_VERSION, "error": "SUPABASE_URL ausente"}
    headers = {"apikey": SUPABASE_KEY or "", "Authorization": f"Bearer {SUPABASE_KEY or ''}"}
    result = await async_request_json("GET", f"{url}/rest/v1/", headers, None, 15)
    return {
        "success": bool(result.get("success")),
        "version": APP_VERSION,
        "target": "/rest/v1/",
        "transport": result.get("transport"),
        "status_code": result.get("status_code"),
        "error": str(result.get("error", ""))[:800],
        "raw": str(result.get("raw", ""))[:800],
    }

@app.get("/api/infra/auth-root")
async def infra_auth_root():
    from api.core.config import SUPABASE_URL, SUPABASE_KEY
    from api.core.http_client import async_request_json
    url = str(SUPABASE_URL or "").strip().rstrip("/")
    if not url:
        return {"success": False, "version": APP_VERSION, "error": "SUPABASE_URL ausente"}
    headers = {"apikey": SUPABASE_KEY or "", "Authorization": f"Bearer {SUPABASE_KEY or ''}"}
    result = await async_request_json("GET", f"{url}/auth/v1/settings", headers, None, 15)
    return {
        "success": bool(result.get("success")),
        "version": APP_VERSION,
        "target": "/auth/v1/settings",
        "transport": result.get("transport"),
        "status_code": result.get("status_code"),
        "error": str(result.get("error", ""))[:800],
        "raw": str(result.get("raw", ""))[:800],
    }

@app.get("/api/infra/full")
async def infra_full():
    steps = {}
    try:
        steps["env"] = infra_env()
    except Exception as exc:
        steps["env"] = {"success": False, "error": str(exc)}
    try:
        steps["dns"] = infra_dns()
    except Exception as exc:
        steps["dns"] = {"success": False, "error": str(exc)}
    try:
        steps["https"] = await infra_https()
    except Exception as exc:
        steps["https"] = {"success": False, "error": str(exc)}
    try:
        steps["rest_root"] = await infra_rest_root()
    except Exception as exc:
        steps["rest_root"] = {"success": False, "error": str(exc)}
    try:
        steps["auth_root"] = await infra_auth_root()
    except Exception as exc:
        steps["auth_root"] = {"success": False, "error": str(exc)}
    try:
        steps["select_companies"] = await test_supabase_minimal()
    except Exception as exc:
        steps["select_companies"] = {"success": False, "error": str(exc)}

    summary = {
        "env_ok": bool(steps.get("env", {}).get("supabase_url", {}).get("present") and steps.get("env", {}).get("service_role_or_key", {}).get("present")),
        "dns_ok": bool(steps.get("dns", {}).get("success")),
        "https_reached": bool(steps.get("https", {}).get("status_code", 0) != 0),
        "rest_reached": bool(steps.get("rest_root", {}).get("status_code", 0) != 0),
        "auth_reached": bool(steps.get("auth_root", {}).get("status_code", 0) != 0),
        "select_ok": bool(steps.get("select_companies", {}).get("success")),
    }

    if not summary["dns_ok"]:
        diagnosis = "Falha em DNS/hostname da SUPABASE_URL."
    elif not summary["https_reached"]:
        diagnosis = "DNS resolveu, mas HTTPS não abriu a conexão."
    elif not summary["rest_reached"]:
        diagnosis = "HTTPS respondeu, mas REST do Supabase não respondeu corretamente."
    elif not summary["select_ok"]:
        diagnosis = "REST respondeu, mas SELECT falhou. Verifique tabela, schema, RLS/policies ou chave."
    else:
        diagnosis = "Infraestrutura Supabase OK."

    return {"success": True, "version": APP_VERSION, "summary": summary, "diagnosis": diagnosis, "steps": steps}


@app.get("/supabase-audit-sql", response_class=HTMLResponse)
async def supabase_audit_sql_page():
    sql = open("supabase_audit_and_fix.sql", "r", encoding="utf-8").read()
    safe_sql = sql.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    content = f"<div class='card'><h2>SQL Auditoria e Correção Supabase</h2><p>Copie este SQL e rode no Supabase SQL Editor.</p><pre>{safe_sql}</pre></div>"
    return HTMLResponse(shell("SQL Supabase Audit", content))




# =========================
# SPRINT 5 - CONNECTIVITY ANALYZER
# =========================

@app.get("/connectivity", response_class=HTMLResponse)
async def connectivity_page():
    content = """
<div class='card'>
<h2>Supabase Connectivity Analyzer</h2>
<p>Diagnóstico isolado de conexão: variáveis, URL, DNS, porta, HTTPS, REST e Auth.</p>
<a class='btn' href='/api/connectivity/full'>Executar análise completa</a>
<a class='btn' href='/api/connectivity/env'>Variáveis</a>
<a class='btn' href='/api/connectivity/dns'>DNS</a>
<a class='btn' href='/api/connectivity/socket'>Socket 443</a>
<a class='btn' href='/api/connectivity/https'>HTTPS</a>
<a class='btn' href='/api/connectivity/rest'>REST</a>
<a class='btn' href='/api/connectivity/auth'>AUTH</a>
</div>
"""
    return HTMLResponse(shell("Connectivity Analyzer", content))

def mask_secret(v):
    if not v:
        return {"present": False, "length": 0, "preview": ""}
    v = str(v).strip()
    return {"present": True, "length": len(v), "preview": (v[:10] + "..." + v[-6:]) if len(v) > 18 else v[:4] + "..."}

def get_supabase_host():
    from urllib.parse import urlparse
    from api.core.config import SUPABASE_URL
    url = str(SUPABASE_URL or "").strip()
    parsed = urlparse(url)
    return url, parsed.hostname or ""

@app.get("/api/connectivity/env")
def connectivity_env():
    from api.core.config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_ANON_KEY
    url = str(SUPABASE_URL or "").strip()
    return {
        "success": True,
        "version": APP_VERSION,
        "supabase_url": mask_secret(url),
        "url_validation": {
            "starts_with_https": url.startswith("https://"),
            "ends_with_supabase_co": url.endswith(".supabase.co"),
            "has_space": " " in url,
            "has_line_break": "\\n" in url or "\\r" in url,
            "looks_like_placeholder": "seuprojeto" in url.lower() or "xxxx" in url.lower(),
        },
        "service_role_key": mask_secret(SUPABASE_KEY),
        "anon_key": mask_secret(SUPABASE_ANON_KEY),
    }

@app.get("/api/connectivity/dns")
def connectivity_dns():
    import socket
    url, host = get_supabase_host()
    if not host:
        return {"success": False, "version": APP_VERSION, "error": "Hostname ausente na SUPABASE_URL", "url": mask_secret(url)}
    try:
        info = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        ips = sorted(set([item[4][0] for item in info]))
        return {"success": True, "version": APP_VERSION, "host": host, "ips": ips[:20], "count": len(ips)}
    except Exception as exc:
        return {"success": False, "version": APP_VERSION, "host": host, "error_type": exc.__class__.__name__, "error": str(exc)}

@app.get("/api/connectivity/socket")
def connectivity_socket():
    import socket, time
    url, host = get_supabase_host()
    if not host:
        return {"success": False, "version": APP_VERSION, "error": "Hostname ausente"}
    start = time.time()
    try:
        with socket.create_connection((host, 443), timeout=8) as s:
            elapsed = round((time.time() - start) * 1000, 2)
            return {"success": True, "version": APP_VERSION, "host": host, "port": 443, "elapsed_ms": elapsed, "message": "Socket TCP 443 abriu"}
    except Exception as exc:
        elapsed = round((time.time() - start) * 1000, 2)
        return {"success": False, "version": APP_VERSION, "host": host, "port": 443, "elapsed_ms": elapsed, "error_type": exc.__class__.__name__, "error": str(exc)}

@app.get("/api/connectivity/https")
async def connectivity_https():
    from api.core.config import SUPABASE_URL
    from api.core.http_client import async_request_json
    url = str(SUPABASE_URL or "").strip().rstrip("/")
    if not url:
        return {"success": False, "version": APP_VERSION, "error": "SUPABASE_URL ausente"}
    res = await async_request_json("GET", url, headers={"User-Agent": "CommerceHubConnectivity/1.0"}, payload=None, timeout=20)
    return {"success": res.get("status_code", 0) != 0, "version": APP_VERSION, "transport": res.get("transport"), "status_code": res.get("status_code"), "error": str(res.get("error", ""))[:1000], "raw": str(res.get("raw", ""))[:1000]}

@app.get("/api/connectivity/rest")
async def connectivity_rest():
    from api.core.config import SUPABASE_URL, SUPABASE_KEY
    from api.core.http_client import async_request_json
    url = str(SUPABASE_URL or "").strip().rstrip("/")
    headers = {"apikey": SUPABASE_KEY or "", "Authorization": f"Bearer {SUPABASE_KEY or ''}", "User-Agent": "CommerceHubConnectivity/1.0"}
    res = await async_request_json("GET", f"{url}/rest/v1/?select=*", headers=headers, payload=None, timeout=20)
    return {"success": bool(res.get("success")), "version": APP_VERSION, "transport": res.get("transport"), "status_code": res.get("status_code"), "error": str(res.get("error", ""))[:1000], "raw": str(res.get("raw", ""))[:1000]}

@app.get("/api/connectivity/auth")
async def connectivity_auth():
    from api.core.config import SUPABASE_URL, SUPABASE_KEY
    from api.core.http_client import async_request_json
    url = str(SUPABASE_URL or "").strip().rstrip("/")
    headers = {"apikey": SUPABASE_KEY or "", "Authorization": f"Bearer {SUPABASE_KEY or ''}", "User-Agent": "CommerceHubConnectivity/1.0"}
    res = await async_request_json("GET", f"{url}/auth/v1/settings", headers=headers, payload=None, timeout=20)
    return {"success": bool(res.get("success")), "version": APP_VERSION, "transport": res.get("transport"), "status_code": res.get("status_code"), "error": str(res.get("error", ""))[:1000], "raw": str(res.get("raw", ""))[:1000]}

@app.get("/api/connectivity/full")
async def connectivity_full():
    steps = {}
    for name, fn in [
        ("env", connectivity_env),
        ("dns", connectivity_dns),
        ("socket", connectivity_socket),
    ]:
        try:
            steps[name] = fn()
        except Exception as exc:
            steps[name] = {"success": False, "error_type": exc.__class__.__name__, "error": str(exc)}
    for name, fn in [
        ("https", connectivity_https),
        ("rest", connectivity_rest),
        ("auth", connectivity_auth),
        ("select_companies", test_supabase_minimal),
    ]:
        try:
            steps[name] = await fn()
        except Exception as exc:
            steps[name] = {"success": False, "error_type": exc.__class__.__name__, "error": str(exc)}

    summary = {
        "env_ok": bool(steps.get("env", {}).get("supabase_url", {}).get("present") and steps.get("env", {}).get("service_role_key", {}).get("present")),
        "dns_ok": bool(steps.get("dns", {}).get("success")),
        "socket_ok": bool(steps.get("socket", {}).get("success")),
        "https_reached": bool(steps.get("https", {}).get("status_code", 0) != 0),
        "rest_ok": bool(steps.get("rest", {}).get("success")),
        "auth_ok": bool(steps.get("auth", {}).get("success")),
        "select_ok": bool(steps.get("select_companies", {}).get("success")),
    }

    if not summary["env_ok"]:
        diagnosis = "Variáveis ausentes ou inválidas na Vercel."
    elif not summary["dns_ok"]:
        diagnosis = "DNS não resolve o host do Supabase. Verifique SUPABASE_URL."
    elif not summary["socket_ok"]:
        diagnosis = "O ambiente Vercel não consegue abrir TCP 443 para o Supabase."
    elif not summary["https_reached"]:
        diagnosis = "Socket abriu, mas HTTPS falhou."
    elif not summary["rest_ok"]:
        diagnosis = "HTTPS chegou, mas REST/PostgREST falhou. Verifique key/schema/permissões."
    elif not summary["select_ok"]:
        diagnosis = "REST respondeu, mas SELECT falhou. Verifique tabelas/RLS/policies."
    else:
        diagnosis = "Conectividade Supabase OK."

    return {"success": True, "version": APP_VERSION, "summary": summary, "diagnosis": diagnosis, "steps": steps}




# =========================
# SPRINT 6 - VERCEL ENV AUDIT
# =========================

@app.get("/vercel-env", response_class=HTMLResponse)
async def vercel_env_page():
    content = """
<div class='card'>
<h2>Auditoria Variáveis Vercel</h2>
<p>Verifica nomes, presença, tamanho, padrão da URL, possíveis valores de exemplo e chaves Supabase.</p>
<a class='btn' href='/api/vercel/env-audit'>Executar auditoria</a>
<a class='btn' href='/api/vercel/env-required'>Variáveis obrigatórias</a>
<a class='btn' href='/api/connectivity/full'>Connectivity Full</a>
</div>
"""
    return HTMLResponse(shell("Vercel Env Audit", content))

def _env_value(name):
    import os
    v = os.getenv(name)
    if v is None:
        return ""
    v = str(v).strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1].strip()
    return v

def _mask_env(v):
    if not v:
        return {"present": False, "length": 0, "preview": ""}
    return {"present": True, "length": len(v), "preview": (v[:12] + "..." + v[-6:]) if len(v) > 24 else v[:6] + "..."}

def _classify_supabase_url(url):
    import re
    issues = []
    ok = True
    if not url:
        return {"ok": False, "issues": ["SUPABASE_URL ausente"]}
    if not url.startswith("https://"):
        ok = False; issues.append("URL precisa começar com https://")
    if "seu-projeto" in url.lower() or "example" in url.lower() or "xxxx" in url.lower():
        ok = False; issues.append("URL parece placeholder/exemplo")
    if " " in url or "\n" in url or "\r" in url:
        ok = False; issues.append("URL contém espaço ou quebra de linha")
    if not url.endswith(".supabase.co"):
        ok = False; issues.append("URL normalmente deve terminar com .supabase.co")
    host_part = url.replace("https://", "").replace(".supabase.co", "")
    if len(host_part) < 10:
        ok = False; issues.append("Project ref parece curto demais")
    if not re.match(r"^https://[a-z0-9]+\.supabase\.co$", url):
        issues.append("Formato esperado: https://PROJECTREF.supabase.co")
    return {"ok": ok, "issues": issues, "project_ref_preview": host_part[:6] + "..." if host_part else ""}

def _classify_jwt_key(key):
    issues = []
    ok = True
    if not key:
        return {"ok": False, "issues": ["chave ausente"]}
    if " " in key or "\n" in key or "\r" in key:
        ok = False; issues.append("chave contém espaço ou quebra de linha")
    if key.lower().startswith("eyj") is False:
        issues.append("chave Supabase normalmente começa com eyJ")
    if len(key) < 100:
        ok = False; issues.append("chave parece curta demais")
    if "seu" in key.lower() or "xxxx" in key.lower() or "example" in key.lower():
        ok = False; issues.append("chave parece placeholder/exemplo")
    return {"ok": ok, "issues": issues}

@app.get("/api/vercel/env-required")
def vercel_env_required():
    return {
        "success": True,
        "version": APP_VERSION,
        "required": [
            "SUPABASE_URL",
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_ANON_KEY",
            "ML_CLIENT_ID",
            "ML_CLIENT_SECRET",
            "ML_REDIRECT_URI"
        ],
        "accepted_fallbacks": {
            "SUPABASE_URL": ["NEXT_PUBLIC_SUPABASE_URL"],
            "SUPABASE_SERVICE_ROLE_KEY": ["SUPABASE_KEY", "SUPABASE_ANON_KEY"],
            "SUPABASE_ANON_KEY": ["NEXT_PUBLIC_SUPABASE_ANON_KEY"]
        },
        "important": "Para produção, use SUPABASE_SERVICE_ROLE_KEY no backend. Não use placeholder como https://seu-projeto.supabase.co."
    }

@app.get("/api/vercel/env-audit")
def vercel_env_audit():
    names = [
        "SUPABASE_URL",
        "NEXT_PUBLIC_SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_KEY",
        "SUPABASE_ANON_KEY",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY",
        "ML_CLIENT_ID",
        "ML_CLIENT_SECRET",
        "ML_REDIRECT_URI",
        "APP_URL"
    ]

    values = {name: _env_value(name) for name in names}
    loaded_url = _env_value("SUPABASE_URL") or _env_value("NEXT_PUBLIC_SUPABASE_URL")
    loaded_key = _env_value("SUPABASE_SERVICE_ROLE_KEY") or _env_value("SUPABASE_KEY") or _env_value("SUPABASE_ANON_KEY")
    loaded_anon = _env_value("SUPABASE_ANON_KEY") or _env_value("NEXT_PUBLIC_SUPABASE_ANON_KEY")

    report = {name: _mask_env(value) for name, value in values.items()}

    url_check = _classify_supabase_url(loaded_url)
    service_key_check = _classify_jwt_key(loaded_key)
    anon_key_check = _classify_jwt_key(loaded_anon)

    diagnosis = []
    if not url_check["ok"]:
        diagnosis.append("Corrigir SUPABASE_URL na Vercel.")
    if "placeholder" in " ".join(url_check.get("issues", [])).lower():
        diagnosis.append("A URL carregada parece ser exemplo/placeholder.")
    if not service_key_check["ok"]:
        diagnosis.append("Corrigir SUPABASE_SERVICE_ROLE_KEY.")
    if not anon_key_check["ok"]:
        diagnosis.append("Adicionar/corrigir SUPABASE_ANON_KEY.")
    if not diagnosis:
        diagnosis.append("Variáveis parecem válidas pelo formato. Próximo teste: connectivity/full.")

    return {
        "success": True,
        "version": APP_VERSION,
        "loaded": {
            "supabase_url": _mask_env(loaded_url),
            "service_role_or_key": _mask_env(loaded_key),
            "anon_key": _mask_env(loaded_anon)
        },
        "checks": {
            "supabase_url": url_check,
            "service_role_or_key": service_key_check,
            "anon_key": anon_key_check
        },
        "all_variables_masked": report,
        "diagnosis": diagnosis,
        "next_steps": [
            "Na Vercel > Project > Environment Variables, corrija SUPABASE_URL com a URL real do Supabase.",
            "Corrija SUPABASE_SERVICE_ROLE_KEY com a service_role key real do Supabase.",
            "Corrija SUPABASE_ANON_KEY com a anon public key real.",
            "Depois faça Redeploy e teste /api/connectivity/full."
        ]
    }




# =========================
# SPRINT 7 - ENV ERROR FINDER
# =========================

@app.get("/env-finder", response_class=HTMLResponse)
async def env_finder_page():
    content = """
<div class='card'>
<h2>Env Error Finder</h2>
<p>Identifica exatamente erros de URL, service role, anon key, aspas, espaços, placeholder e nomes incorretos.</p>
<a class='btn' href='/api/env-finder/full'>Executar diagnóstico completo</a>
<a class='btn' href='/api/env-finder/checklist'>Checklist de correção</a>
<a class='btn' href='/api/vercel/env-audit'>Auditoria anterior</a>
</div>
"""
    return HTMLResponse(shell("Env Error Finder", content))

def _raw_env(name):
    import os
    return os.getenv(name)

def _clean_env_value(value):
    if value is None:
        return ""
    value = str(value)
    cleaned = value.strip()
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
        cleaned = cleaned[1:-1].strip()
    return cleaned

def _masked(value):
    if not value:
        return {"present": False, "length": 0, "preview": ""}
    return {"present": True, "length": len(value), "preview": (value[:10] + "..." + value[-6:]) if len(value) > 22 else value[:5] + "..."}

def _analyze_var(name, expected_type):
    import re
    raw = _raw_env(name)
    cleaned = _clean_env_value(raw)
    issues = []
    severity = "ok"

    if raw is None:
        return {
            "name": name,
            "present": False,
            "expected_type": expected_type,
            "status": "missing",
            "severity": "critical",
            "raw_length": 0,
            "cleaned": _masked(""),
            "issues": [f"{name} não existe na Vercel."]
        }

    if raw != cleaned:
        issues.append("Valor tem espaços, aspas ou quebra de linha antes/depois. O sistema limpou para testar, mas corrija na Vercel.")

    if "\n" in str(raw) or "\r" in str(raw):
        issues.append("Valor contém quebra de linha.")
    if str(raw).startswith(" ") or str(raw).endswith(" "):
        issues.append("Valor contém espaço no início ou no fim.")
    if str(raw).startswith('"') or str(raw).startswith("'"):
        issues.append("Valor pode ter aspas no início.")
    if str(raw).endswith('"') or str(raw).endswith("'"):
        issues.append("Valor pode ter aspas no fim.")

    low = cleaned.lower()

    if expected_type == "supabase_url":
        if not cleaned.startswith("https://"):
            issues.append("SUPABASE_URL precisa começar com https://")
        if not cleaned.endswith(".supabase.co"):
            issues.append("SUPABASE_URL precisa terminar com .supabase.co")
        if "seu-projeto" in low or "seuprojeto" in low or "projectref" in low or "example" in low or "xxxx" in low:
            issues.append("SUPABASE_URL é placeholder/exemplo, não é URL real.")
        if not re.match(r"^https://[a-z0-9]{15,30}\.supabase\.co$", cleaned):
            issues.append("Formato esperado: https://PROJECTREF.supabase.co com project ref real em minúsculas.")
        if len(cleaned) < 35:
            issues.append("SUPABASE_URL parece curta demais.")

    if expected_type == "jwt":
        parts = cleaned.split(".")
        if len(parts) != 3:
            issues.append("Chave não parece JWT válida. Uma chave Supabase normalmente tem 3 partes separadas por ponto.")
        if not cleaned.startswith("eyJ"):
            issues.append("Chave Supabase normalmente começa com eyJ.")
        if len(cleaned) < 120:
            issues.append("Chave parece curta demais. Service Role/Anon normalmente tem mais de 120 caracteres.")
        if "service_role" == low or "anon" == low or "sua-chave" in low or "xxxx" in low or "example" in low:
            issues.append("Chave parece placeholder/exemplo.")
        if " " in cleaned:
            issues.append("Chave contém espaço interno.")

    if expected_type == "url":
        if not cleaned.startswith("http"):
            issues.append("URL precisa começar com http ou https.")

    if issues:
        severity = "critical" if any("placeholder" in x.lower() or "não existe" in x.lower() or "curta demais" in x.lower() for x in issues) else "warning"

    return {
        "name": name,
        "present": True,
        "expected_type": expected_type,
        "status": "ok" if not issues else "invalid",
        "severity": severity,
        "raw_length": len(str(raw)),
        "cleaned": _masked(cleaned),
        "issues": issues
    }

@app.get("/api/env-finder/full")
def env_finder_full():
    checks = [
        _analyze_var("SUPABASE_URL", "supabase_url"),
        _analyze_var("SUPABASE_SERVICE_ROLE_KEY", "jwt"),
        _analyze_var("SUPABASE_ANON_KEY", "jwt"),
        _analyze_var("ML_CLIENT_ID", "text"),
        _analyze_var("ML_CLIENT_SECRET", "text"),
        _analyze_var("ML_REDIRECT_URI", "url"),
    ]

    fallback_checks = [
        _analyze_var("NEXT_PUBLIC_SUPABASE_URL", "supabase_url"),
        _analyze_var("SUPABASE_KEY", "jwt"),
        _analyze_var("NEXT_PUBLIC_SUPABASE_ANON_KEY", "jwt"),
    ]

    critical = [c for c in checks if c["severity"] == "critical"]
    warnings = [c for c in checks + fallback_checks if c["severity"] == "warning"]

    exact_errors = []
    for c in checks:
        for issue in c["issues"]:
            exact_errors.append(f"{c['name']}: {issue}")

    if not exact_errors:
        exact_errors.append("Nenhum erro crítico encontrado no formato das variáveis principais.")

    return {
        "success": True,
        "version": APP_VERSION,
        "production_ready": len(critical) == 0,
        "critical_count": len(critical),
        "warning_count": len(warnings),
        "exact_errors": exact_errors,
        "required_checks": checks,
        "fallback_checks": fallback_checks,
        "decision": "Corrigir variáveis críticas na Vercel e fazer Redeploy." if critical else "Variáveis principais parecem corretas. Próximo passo: testar /api/connectivity/full.",
        "next_test_after_fix": "/api/connectivity/full"
    }

@app.get("/api/env-finder/checklist")
def env_finder_checklist():
    return {
        "success": True,
        "version": APP_VERSION,
        "where_to_fix": "Vercel > Project > Settings > Environment Variables",
        "set_exactly_these_names": {
            "SUPABASE_URL": "Copiar do Supabase > Project Settings > API > Project URL",
            "SUPABASE_SERVICE_ROLE_KEY": "Copiar do Supabase > Project Settings > API > service_role secret. Backend only.",
            "SUPABASE_ANON_KEY": "Copiar do Supabase > Project Settings > API > anon public.",
            "ML_CLIENT_ID": "Mercado Livre App ID",
            "ML_CLIENT_SECRET": "Mercado Livre Client Secret",
            "ML_REDIRECT_URI": "https://commercehub-vercel-mvp.vercel.app/mercadolivre/callback"
        },
        "important_rules": [
            "Não use https://seu-projeto.supabase.co.",
            "Não use aspas.",
            "Não deixe espaços no começo ou no fim.",
            "Service Role e Anon Key normalmente começam com eyJ e possuem 3 partes separadas por ponto.",
            "Depois de alterar variáveis na Vercel, clique em Redeploy. Só alterar variável não atualiza o deploy atual."
        ],
        "after_redeploy_test": [
            "/api/health",
            "/api/env-finder/full",
            "/api/connectivity/full",
            "/api/test/supabase",
            "/api/test/supabase-insert"
        ]
    }




# =========================
# SPRINT 8 - RAW HTTP DIAGNOSTIC
# =========================

@app.get("/raw-http", response_class=HTMLResponse)
async def raw_http_page():
    content = """
<div class='card'>
<h2>Raw HTTP Diagnostic</h2>
<p>Teste direto e bruto contra Supabase, sem camada intermediária. Captura status HTTP, headers, body e traceback.</p>
<a class='btn' href='/api/raw/supabase-url'>URL carregada</a>
<a class='btn' href='/api/raw/rest-open'>REST sem auth</a>
<a class='btn' href='/api/raw/rest-auth'>REST com service role</a>
<a class='btn' href='/api/raw/select-companies'>SELECT companies raw</a>
<a class='btn' href='/api/raw/full'>Diagnóstico completo</a>
</div>
"""
    return HTMLResponse(shell("Raw HTTP Diagnostic", content))

def _raw_mask(v):
    if not v:
        return {"present": False, "length": 0, "preview": ""}
    v = str(v).strip()
    return {"present": True, "length": len(v), "preview": (v[:14] + "..." + v[-8:]) if len(v) > 26 else v[:6] + "..."}

def _raw_clean(v):
    if v is None:
        return ""
    v = str(v).strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1].strip()
    return v

def _raw_env():
    import os
    url = _raw_clean(os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL"))
    service = _raw_clean(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY"))
    anon = _raw_clean(os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY"))
    return url, service, anon

async def _raw_httpx_request(label, method, url, headers=None, json_body=None):
    import traceback
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            resp = await client.request(method, url, headers=headers or {}, json=json_body)
            return {
                "label": label,
                "success": 200 <= resp.status_code < 400,
                "transport": "httpx_raw",
                "method": method,
                "url_masked": _raw_mask(url),
                "status_code": resp.status_code,
                "headers": {k: v for k, v in list(resp.headers.items())[:20]},
                "body": resp.text[:3000],
                "error": "",
            }
    except Exception as exc:
        return {
            "label": label,
            "success": False,
            "transport": "httpx_raw",
            "method": method,
            "url_masked": _raw_mask(url),
            "status_code": 0,
            "headers": {},
            "body": "",
            "error_type": exc.__class__.__name__,
            "error": str(exc),
            "traceback": traceback.format_exc()[-5000:],
        }

@app.get("/api/raw/supabase-url")
def raw_supabase_url():
    from urllib.parse import urlparse
    url, service, anon = _raw_env()
    parsed = urlparse(url) if url else None
    return {
        "success": True,
        "version": APP_VERSION,
        "supabase_url": _raw_mask(url),
        "service_role": _raw_mask(service),
        "anon_key": _raw_mask(anon),
        "parsed": {
            "scheme": parsed.scheme if parsed else "",
            "hostname": parsed.hostname if parsed else "",
            "path": parsed.path if parsed else "",
        },
        "flags": {
            "url_is_placeholder": "seu-projeto" in url.lower() or "projectref" in url.lower() or "xxxx" in url.lower(),
            "service_key_too_short": len(service) < 120,
            "anon_key_missing": not bool(anon),
            "anon_key_too_short": bool(anon) and len(anon) < 120,
        }
    }

@app.get("/api/raw/rest-open")
async def raw_rest_open():
    url, service, anon = _raw_env()
    if not url:
        return {"success": False, "version": APP_VERSION, "error": "SUPABASE_URL ausente"}
    return await _raw_httpx_request("rest_open_no_auth", "GET", f"{url.rstrip('/')}/rest/v1/")

@app.get("/api/raw/rest-auth")
async def raw_rest_auth():
    url, service, anon = _raw_env()
    if not url:
        return {"success": False, "version": APP_VERSION, "error": "SUPABASE_URL ausente"}
    headers = {
        "apikey": service,
        "Authorization": f"Bearer {service}",
        "Accept": "application/json",
        "User-Agent": "CommerceHubRawDiagnostic/1.0",
    }
    return await _raw_httpx_request("rest_root_with_service_role", "GET", f"{url.rstrip('/')}/rest/v1/", headers=headers)

@app.get("/api/raw/select-companies")
async def raw_select_companies():
    url, service, anon = _raw_env()
    if not url:
        return {"success": False, "version": APP_VERSION, "error": "SUPABASE_URL ausente"}
    headers = {
        "apikey": service,
        "Authorization": f"Bearer {service}",
        "Accept": "application/json",
        "User-Agent": "CommerceHubRawDiagnostic/1.0",
    }
    return await _raw_httpx_request(
        "select_companies_with_service_role",
        "GET",
        f"{url.rstrip('/')}/rest/v1/companies?select=*&limit=1",
        headers=headers
    )

@app.get("/api/raw/full")
async def raw_full():
    steps = {}
    try:
        steps["env"] = raw_supabase_url()
    except Exception as exc:
        steps["env"] = {"success": False, "error": str(exc)}
    try:
        steps["rest_open"] = await raw_rest_open()
    except Exception as exc:
        steps["rest_open"] = {"success": False, "error": str(exc)}
    try:
        steps["rest_auth"] = await raw_rest_auth()
    except Exception as exc:
        steps["rest_auth"] = {"success": False, "error": str(exc)}
    try:
        steps["select_companies"] = await raw_select_companies()
    except Exception as exc:
        steps["select_companies"] = {"success": False, "error": str(exc)}

    env = steps.get("env", {})
    flags = env.get("flags", {})
    select_status = steps.get("select_companies", {}).get("status_code", 0)

    if flags.get("url_is_placeholder"):
        diagnosis = "SUPABASE_URL ainda é placeholder. Corrija na Vercel."
    elif flags.get("service_key_too_short"):
        diagnosis = "SUPABASE_SERVICE_ROLE_KEY está curta/inválida. Corrija na Vercel."
    elif select_status == 401:
        diagnosis = "Supabase respondeu 401: chave inválida ou Authorization incorreto."
    elif select_status == 403:
        diagnosis = "Supabase respondeu 403: permissão/RLS/policy."
    elif select_status == 404:
        diagnosis = "Supabase respondeu 404: tabela/schema/URL REST."
    elif select_status == 200:
        diagnosis = "Conexão raw OK. O problema está em outra camada."
    elif select_status == 0:
        diagnosis = "Não houve resposta HTTP. Veja traceback em steps.select_companies."
    else:
        diagnosis = f"Resposta HTTP inesperada: {select_status}."

    return {
        "success": True,
        "version": APP_VERSION,
        "diagnosis": diagnosis,
        "steps": steps
    }


# =========================
# V5 - ENVIRONMENT MANAGER
# =========================

@app.get("/environment", response_class=HTMLResponse)
async def environment_page():
    content = """
<div class='card'>
<h2>CommerceHub Environment Manager</h2>
<p>Validação final de variáveis, Supabase, REST, Auth, leitura, escrita e diagnóstico claro.</p>
<a class='btn' href='/api/environment/full'>Diagnóstico completo</a>
<a class='btn' href='/api/environment/required'>Variáveis obrigatórias</a>
<a class='btn' href='/api/raw/full'>Raw HTTP</a>
<a class='btn' href='/api/test/supabase'>Teste SELECT</a>
<a class='btn' href='/api/test/supabase-insert'>Teste INSERT</a>
</div>
"""
    return HTMLResponse(shell("Environment Manager", content))

@app.get("/api/environment/required")
def environment_required():
    return {
        "success": True,
        "version": APP_VERSION,
        "vercel_path": "Vercel > Project > Settings > Environment Variables",
        "supabase_path": "Supabase > Project Settings > API",
        "required": {
            "SUPABASE_URL": "Project URL real. Exemplo correto: https://xxxxxxxxxxxxxxxxxxxx.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "service_role secret key real. Backend only.",
            "SUPABASE_ANON_KEY": "anon public key real.",
            "ML_CLIENT_ID": "Client ID do app Mercado Livre.",
            "ML_CLIENT_SECRET": "Client Secret do app Mercado Livre.",
            "ML_REDIRECT_URI": "https://commercehub-vercel-mvp.vercel.app/mercadolivre/callback"
        },
        "rules": [
            "Não use placeholders como https://SEU-PROJETO.supabase.co.",
            "Não coloque aspas nas variáveis.",
            "Não deixe espaço no começo/fim.",
            "Service Role e Anon Key normalmente começam com eyJ e têm 3 partes separadas por ponto.",
            "Depois de salvar as variáveis, faça Redeploy."
        ]
    }

@app.get("/api/environment/full")
async def environment_full():
    from api.core.env_manager import full_env_report
    env_report = full_env_report()
    if env_report.get("production_ready_supabase"):
        try:
            raw_report = await raw_full()
        except Exception as exc:
            raw_report = {"success": False, "error": str(exc)}
        try:
            select_report = await test_supabase_minimal()
        except Exception as exc:
            select_report = {"success": False, "error": str(exc)}
        try:
            insert_report = await test_supabase_insert()
        except Exception as exc:
            insert_report = {"success": False, "error": str(exc)}
    else:
        raw_report = {"skipped": True, "reason": "Variáveis Supabase ainda inválidas."}
        select_report = {"skipped": True, "reason": "Variáveis Supabase ainda inválidas."}
        insert_report = {"skipped": True, "reason": "Variáveis Supabase ainda inválidas."}
    if not env_report.get("production_ready_supabase"):
        diagnosis = "Corrigir variáveis Supabase na Vercel antes de testar banco."
    elif select_report and select_report.get("success") and insert_report and insert_report.get("success"):
        diagnosis = "Ambiente Supabase pronto para operação."
    elif raw_report and raw_report.get("diagnosis"):
        diagnosis = raw_report.get("diagnosis")
    else:
        diagnosis = "Variáveis parecem corretas, mas os testes de banco ainda falharam. Veja raw_report/select_report."
    return {"success": True, "version": APP_VERSION, "diagnosis": diagnosis, "environment": env_report, "raw_report": raw_report, "select_report": select_report, "insert_report": insert_report}
