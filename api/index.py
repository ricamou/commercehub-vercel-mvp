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
