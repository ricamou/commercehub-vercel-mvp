from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import json, uuid, hashlib, hmac, base64, time, csv, io, os, mimetypes, xml.etree.ElementTree as ET
from urllib.parse import quote, urlparse
from api.core.config import APP_VERSION, DEFAULT_COMPANY_ID
from api.db import store
from api.services.mercadolivre import auth_url, exchange_code, ml_request, get_token
from api.ui.templates import shell, btn

app = FastAPI(title="CommerceHub Enterprise V5", version=APP_VERSION)

def state():
    return {"version": APP_VERSION, "mode": store.mode(), "supabase_configured": store.configured()}

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "commercehub", **state()}

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    token = await get_token()
    content = f"<div class='grid'><div class='metric'><span>Sistema</span><strong>OK</strong></div><div class='metric'><span>Banco</span><strong>{store.mode().upper()}</strong></div><div class='metric'><span>ML</span><strong>{'ON' if token else 'OFF'}</strong></div><div class='metric'><span>Versão</span><strong>V4</strong></div></div><div class='card'><h2>CommerceHub Enterprise V5 - Sprint 1</h2><p>Base limpa: login, empresas, Supabase e OAuth Mercado Livre.</p>{btn('/setup','Setup')}{btn('/login','Login')}{btn('/companies','Empresas')}{btn('/mercado-livre','Mercado Livre')}</div>"
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
async def login_page(request: Request):
    current = auth_user_from_request(request)
    if current:
        return RedirectResponse("/dashboard", status_code=303)

    error = request.query_params.get("error", "")
    notice = f"<p style='color:#b91c1c;font-weight:bold'>{error}</p>" if error else ""
    content = f"""
<div class='card' style='max-width:520px'>
<h2>Entrar no CommerceHub</h2>
<p>Use seu usuário administrador para acessar o sistema.</p>
{notice}
<form method='post' action='/api/login'>
<label>Email</label>
<input name='email' value='admin@commercehub.local' autocomplete='email' required>
<label>Senha</label>
<input name='password' type='password' autocomplete='current-password' required>
<button type='submit'>Entrar</button>
</form>
<p style='color:#64748b;font-size:13px'>Sessão segura com token JWT HS256 em cookie HttpOnly.</p>
</div>
"""
    return HTMLResponse(shell("Login", content))


@app.post("/api/login")
async def login(request: Request):
    form = await request.form()
    email = str(form.get("email") or "").strip().lower()
    password = str(form.get("password") or "")

    if not email or not password:
        return RedirectResponse("/login?error=Informe+email+e+senha", status_code=303)

    safe_email = quote(email, safe="@._+-")
    users = await store.select("users_app", f"select=*&email=eq.{safe_email}&limit=1")
    rows = users.get("data") or []
    expected = hashlib.sha256(password.encode("utf-8")).hexdigest()

    if not rows or not hmac.compare_digest(str(rows[0].get("password_hash") or ""), expected):
        return RedirectResponse("/login?error=Email+ou+senha+inválidos", status_code=303)

    user = rows[0]
    if str(user.get("status") or "").lower() != "active":
        return RedirectResponse("/login?error=Usuário+inativo", status_code=303)

    token = create_session_token(user)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(
        key="commercehub_session",
        value=token,
        max_age=SESSION_HOURS * 3600,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )

    await store.insert("logs", {
        "company_id": user.get("company_id") or DEFAULT_COMPANY_ID,
        "event_type": "login_success",
        "level": "info",
        "message": f"Login realizado por {email}",
        "payload": {"user_id": user.get("id"), "role": user.get("role")}
    })
    return response


@app.get("/logout")
async def logout(request: Request):
    current = auth_user_from_request(request)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("commercehub_session", path="/")

    if current:
        await store.insert("logs", {
            "company_id": current.get("company_id") or DEFAULT_COMPANY_ID,
            "event_type": "logout",
            "level": "info",
            "message": f"Logout realizado por {current.get('email')}",
            "payload": {"user_id": current.get("sub")}
        })
    return response


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    user = auth_user_from_request(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    content = f"""
<div class='card'>
<h2>Meu Perfil</h2>
<table>
<tr><th>Nome</th><td>{user.get('name','')}</td></tr>
<tr><th>Email</th><td>{user.get('email','')}</td></tr>
<tr><th>Perfil</th><td>{user.get('role','')}</td></tr>
<tr><th>Empresa</th><td>{user.get('company_id','')}</td></tr>
<tr><th>Sessão expira</th><td>{user.get('exp','')}</td></tr>
</table>
<a class='btn' href='/api/auth/status'>Status da sessão</a>
<a class='btn' href='/logout'>Sair</a>
</div>
"""
    return HTMLResponse(shell("Meu Perfil", content))


@app.get("/api/auth/status")
async def auth_status(request: Request):
    user = auth_user_from_request(request)
    return {
        "success": True,
        "version": APP_VERSION,
        "authenticated": bool(user),
        "auth_required": AUTH_REQUIRED,
        "user": user or None,
        "roles": ["admin", "operator", "viewer"]
    }


@app.get("/api/auth/admin-check")
async def auth_admin_check(request: Request):
    user = auth_user_from_request(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Não autenticado"})
    if user.get("role") != "admin":
        return JSONResponse(status_code=403, content={"success": False, "error": "Permissão de administrador necessária"})
    return {"success": True, "message": "Administrador autorizado", "user": user}

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

@app.get("/database", response_class=HTMLResponse)
async def database_page():
    content = """
<div class='card'>
<h2>Database Foundation</h2>
<p>Schema definitivo do CommerceHub Enterprise para Supabase.</p>
<a class='btn' href='/database-sql'>Ver SQL do banco</a>
<a class='btn' href='/api/database/schema-check'>Checar schema</a>
<a class='btn' href='/api/test/supabase'>Teste SELECT</a>
<a class='btn' href='/api/test/supabase-insert'>Teste INSERT</a>
<a class='btn' href='/api/test/supabase-crud'>Teste CRUD</a>
</div>
"""
    return HTMLResponse(shell("Database Foundation", content))

@app.get("/database-sql", response_class=HTMLResponse)
async def database_sql_page():
    sql = open("commercehub_enterprise_schema.sql", "r", encoding="utf-8").read()
    safe_sql = sql.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    content = f"<div class='card'><h2>CommerceHub Enterprise Schema SQL</h2><p>Copie e execute no Supabase > SQL Editor.</p><pre>{safe_sql}</pre></div>"
    return HTMLResponse(shell("Database SQL", content))

@app.get("/api/database/schema-check")
async def database_schema_check():
    expected_tables = ["companies","users_app","settings","suppliers","categories","brands","products","product_images","inventory","inventory_movements","marketplace_accounts","oauth_tokens","listings","orders","order_items","queue","sync_jobs","sync_logs","webhooks","ai_history","logs","audit_logs","notifications"]
    results = {}
    ok_count = 0
    for table in expected_tables:
        try:
            res = await store.select(table, "select=*&limit=1")
            success = bool(res.get("success"))
            if success:
                ok_count += 1
            results[table] = {"ok": success, "status_code": res.get("status_code"), "rows": res.get("rows", 0), "error": str(res.get("error", ""))[:500]}
        except Exception as exc:
            results[table] = {"ok": False, "error": str(exc)[:500]}
    return {"success": ok_count == len(expected_tables), "version": APP_VERSION, "ok_count": ok_count, "total": len(expected_tables), "missing_or_error": [t for t, r in results.items() if not r.get("ok")], "results": results}




# =========================
# SPRINT 10 - CORE OPERATION
# =========================

def _val(row, key, default=""):
    if not isinstance(row, dict):
        return default
    return row.get(key, default)

def _fmt_money(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def _html_table(headers, rows):
    th = "".join([f"<th>{h}</th>" for h in headers])
    trs = []
    for row in rows:
        tds = "".join([f"<td>{c}</td>" for c in row])
        trs.append(f"<tr>{tds}</tr>")
    return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(trs) if trs else '<tr><td colspan=\"20\">Nenhum registro encontrado.</td></tr>'}</tbody></table>"

@app.get("/core", response_class=HTMLResponse)
async def core_page():
    content = """
<div class='card'>
<h2>CommerceHub Core Operation</h2>
<p>Primeiro painel operacional: empresa, usuário, fornecedores, produtos, estoque, logs e Mercado Livre.</p>
<a class='btn' href='/api/core/status'>Status Core</a>
<a class='btn' href='/companies'>Empresas</a>
<a class='btn' href='/users'>Usuários</a>
<a class='btn' href='/suppliers'>Fornecedores</a>
<a class='btn' href='/products'>Produtos</a>
<a class='btn' href='/inventory'>Estoque</a>
<a class='btn' href='/logs'>Logs</a>
</div>
"""
    return HTMLResponse(shell("Core Operation", content))

@app.get("/api/core/status")
async def core_status():
    tables = ["companies", "users_app", "suppliers", "products", "inventory", "logs", "marketplace_accounts", "oauth_tokens", "listings", "orders"]
    counts = {}
    ok = True
    for table in tables:
        res = await store.select(table, "select=*&limit=1000")
        counts[table] = {
            "success": res.get("success", False),
            "rows": res.get("rows", 0),
            "error": res.get("error", "")[:300]
        }
        if not res.get("success"):
            ok = False
    return {
        "success": ok,
        "version": APP_VERSION,
        "core_ready": ok,
        "counts": counts,
        "next": "/dashboard" if ok else "/database-sql"
    }

@app.get("/companies", response_class=HTMLResponse)
async def companies_page():
    res = await store.select("companies", "select=*&order=created_at.desc")
    rows = res.get("data", []) if res.get("success") else []
    table = _html_table(
        ["Nome", "Documento", "Email", "Plano", "Status"],
        [[_val(r,"name"), _val(r,"document"), _val(r,"email"), _val(r,"plan"), _val(r,"status")] for r in rows]
    )
    content = f"""
<div class='card'>
<h2>Empresas</h2>
<p>Multiempresa ativa por company_id.</p>
{table}
<a class='btn' href='/api/core/status'>Status JSON</a>
</div>
"""
    return HTMLResponse(shell("Empresas", content))

@app.get("/users", response_class=HTMLResponse)
async def users_page():
    res = await store.select("users_app", "select=*&order=created_at.desc")
    rows = res.get("data", []) if res.get("success") else []
    table = _html_table(
        ["Nome", "Email", "Perfil", "Status"],
        [[_val(r,"name"), _val(r,"email"), _val(r,"role"), _val(r,"status")] for r in rows]
    )
    content = f"<div class='card'><h2>Usuários</h2>{table}<p>Login inicial: admin@commercehub.local / admin123</p></div>"
    return HTMLResponse(shell("Usuários", content))

@app.get("/suppliers", response_class=HTMLResponse)
async def suppliers_page():
    res = await store.select("suppliers", "select=*&order=created_at.desc")
    rows = res.get("data", []) if res.get("success") else []
    table = _html_table(
        ["Nome", "Tipo", "Status", "Email"],
        [[_val(r,"name"), _val(r,"type"), _val(r,"status"), _val(r,"email")] for r in rows]
    )
    content = f"""
<div class='card'>
<h2>Fornecedores</h2>
{table}
<a class='btn' href='/api/foundation/seed'>Seed inicial</a>
</div>
"""
    return HTMLResponse(shell("Fornecedores", content))

@app.get("/products", response_class=HTMLResponse)
async def products_page():
    return RedirectResponse("/product-master", status_code=303)

@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page():
    res = await store.select("inventory", "select=*&order=created_at.desc")
    rows = res.get("data", []) if res.get("success") else []
    table = _html_table(
        ["SKU", "Qtd", "Reservado", "Disponível", "Status"],
        [[_val(r,"sku"), _val(r,"quantity"), _val(r,"reserved"), _val(r,"available"), _val(r,"status")] for r in rows]
    )
    content = f"<div class='card'><h2>Estoque</h2>{table}</div>"
    return HTMLResponse(shell("Estoque", content))

@app.get("/logs", response_class=HTMLResponse)
async def logs_page():
    res = await store.select("logs", "select=*&order=created_at.desc&limit=50")
    rows = res.get("data", []) if res.get("success") else []
    table = _html_table(
        ["Data", "Tipo", "Nível", "Mensagem"],
        [[_val(r,"created_at"), _val(r,"event_type"), _val(r,"level"), _val(r,"message")] for r in rows]
    )
    content = f"<div class='card'><h2>Logs</h2>{table}</div>"
    return HTMLResponse(shell("Logs", content))

@app.get("/api/core/create-test-product")
async def core_create_test_product():
    import time
    sku = f"CH-AUTO-{int(time.time())}"
    product = {
        "company_id": DEFAULT_COMPANY_ID,
        "sku": sku,
        "name": f"Produto Automático {sku}",
        "brand": "CommerceHub",
        "description": "Produto criado pelo Core Operation para validar gravação real.",
        "cost_price": 35.50,
        "sale_price": 89.90,
        "status": "active",
        "raw_data": {"source": "core_create_test_product", "version": APP_VERSION}
    }
    created = await store.insert("products", product)
    if created.get("success") and created.get("data"):
        product_id = created["data"][0].get("id")
        await store.insert("inventory", {
            "company_id": DEFAULT_COMPANY_ID,
            "product_id": product_id,
            "sku": sku,
            "quantity": 5,
            "reserved": 0,
            "status": "available"
        })
        await store.insert("logs", {
            "company_id": DEFAULT_COMPANY_ID,
            "event_type": "product_created",
            "level": "info",
            "message": f"Produto {sku} criado com sucesso",
            "payload": {"sku": sku}
        })
    return {
        "success": created.get("success", False),
        "version": APP_VERSION,
        "sku": sku,
        "created": created,
        "next": "/products"
    }

@app.get("/api/core/sell-readiness")
async def sell_readiness():
    checks = {}
    for table in ["companies","users_app","suppliers","products","inventory","marketplace_accounts"]:
        res = await store.select(table, "select=*&limit=1")
        checks[table] = res.get("success") and res.get("rows",0) >= 1

    ml = {
        "has_client_id": bool(ML_CLIENT_ID),
        "has_client_secret": bool(ML_CLIENT_SECRET),
        "has_redirect_uri": bool(ML_REDIRECT_URI),
        "has_access_token": bool(ML_ACCESS_TOKEN),
        "has_refresh_token": bool(ML_REFRESH_TOKEN),
    }

    ready_base = all(checks.values())
    ready_ml = ml["has_client_id"] and ml["has_client_secret"] and ml["has_redirect_uri"]

    return {
        "success": True,
        "version": APP_VERSION,
        "base_operational": ready_base,
        "mercado_livre_app_configured": ready_ml,
        "mercado_livre_token_available": ml["has_access_token"],
        "checks": checks,
        "ml": ml,
        "next_step": "Conectar OAuth Mercado Livre" if ready_base and ready_ml and not ml["has_access_token"] else "Executar schema/seed primeiro"
    }




# =========================
# SPRINT 11 - ENTERPRISE DEBUG MODE
# =========================

@app.get("/debug", response_class=HTMLResponse)
async def debug_page():
    content = """
<div class='card'>
<h2>Enterprise Debug Mode</h2>
<p>Diagnóstico profissional de erros, banco, rotas críticas e ambiente.</p>
<a class='btn' href='/api/debug/ping'>Ping Debug</a>
<a class='btn' href='/api/debug/core-status-safe'>Core Status Safe</a>
<a class='btn' href='/api/debug/schema-check-safe'>Schema Check Safe</a>
<a class='btn' href='/api/debug/route-test'>Route Test</a>
<a class='btn' href='/api/environment/full'>Environment Full</a>
<a class='btn' href='/api/raw/full'>Raw HTTP</a>
</div>
"""
    return HTMLResponse(shell("Enterprise Debug Mode", content))

@app.get("/api/debug/ping")
async def debug_ping():
    return {
        "success": True,
        "version": APP_VERSION,
        "debug_mode": True,
        "message": "Enterprise Debug Mode ativo. Erros agora devem retornar JSON detalhado."
    }

@app.get("/api/debug/route-test")
async def debug_route_test():
    async def run():
        return {
            "success": True,
            "version": APP_VERSION,
            "routes": [
                "/api/health",
                "/debug",
                "/api/debug/core-status-safe",
                "/api/debug/schema-check-safe",
                "/api/core/status",
                "/api/database/schema-check",
                "/api/test/supabase",
                "/api/test/supabase-insert",
                "/api/test/supabase-crud",
            ]
        }
    return await safe_route(run, path="/api/debug/route-test")

@app.get("/api/debug/core-status-safe")
async def debug_core_status_safe():
    async def run():
        tables = ["companies", "users_app", "suppliers", "products", "inventory", "logs", "marketplace_accounts", "oauth_tokens", "listings", "orders"]
        counts = {}
        ok = True
        for table in tables:
            res = await store.select(table, "select=*&limit=1000")
            counts[table] = {
                "success": res.get("success", False),
                "rows": res.get("rows", 0),
                "status_code": res.get("status_code"),
                "error": str(res.get("error", ""))[:500]
            }
            if not res.get("success"):
                ok = False
        return {
            "success": ok,
            "version": APP_VERSION,
            "core_ready": ok,
            "counts": counts,
            "next": "/dashboard" if ok else "/database-sql"
        }
    return await safe_route(run, path="/api/debug/core-status-safe")

@app.get("/api/debug/schema-check-safe")
async def debug_schema_check_safe():
    async def run():
        expected_tables = [
            "companies","users_app","settings","suppliers","categories","brands","products",
            "product_images","inventory","inventory_movements","marketplace_accounts",
            "oauth_tokens","listings","orders","order_items","queue","sync_jobs","sync_logs",
            "webhooks","ai_history","logs","audit_logs","notifications"
        ]
        results = {}
        ok_count = 0
        for table in expected_tables:
            res = await store.select(table, "select=*&limit=1")
            success = bool(res.get("success"))
            if success:
                ok_count += 1
            results[table] = {
                "ok": success,
                "status_code": res.get("status_code"),
                "rows": res.get("rows", 0),
                "error": str(res.get("error", ""))[:500],
            }
        return {
            "success": ok_count == len(expected_tables),
            "version": APP_VERSION,
            "ok_count": ok_count,
            "total": len(expected_tables),
            "missing_or_error": [t for t, r in results.items() if not r.get("ok")],
            "results": results
        }
    return await safe_route(run, path="/api/debug/schema-check-safe")

@app.get("/api/debug/force-error")
async def debug_force_error():
    async def run():
        raise RuntimeError("Erro proposital para validar o Enterprise Debug Mode")
    return await safe_route(run, path="/api/debug/force-error")


# =========================
# SPRINT 12 - PYTHON INSPECTOR FIX
# Endpoints independentes de db_select/db_insert para evitar 500 cego.
# =========================

def _s12_mask(v):
    v = str(v or '').strip()
    if not v:
        return {'present': False, 'length': 0, 'preview': ''}
    return {'present': True, 'length': len(v), 'preview': (v[:10] + '...' + v[-6:]) if len(v) > 20 else v[:5] + '...'}

def _s12_error(exc, path=''):
    import traceback, uuid
    return {
        'success': False,
        'version': APP_VERSION,
        'error_id': str(uuid.uuid4()),
        'error_type': type(exc).__name__,
        'message': str(exc),
        'path': path,
        'traceback': traceback.format_exc()[-8000:]
    }

async def _s12_safe(path, fn):
    try:
        return await fn()
    except Exception as exc:
        return _s12_error(exc, path)

async def _s12_select(table, limit=1):
    import os, httpx
    url=(os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL') or '').strip().strip('"').strip("'")
    key=(os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY') or '').strip().strip('"').strip("'")
    if not url: return {'success': False, 'table': table, 'error': 'SUPABASE_URL ausente'}
    if not key: return {'success': False, 'table': table, 'error': 'SUPABASE_SERVICE_ROLE_KEY ausente'}
    headers={'apikey':key,'Authorization':f'Bearer {key}','Accept':'application/json','Content-Type':'application/json'}
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=False) as client:
        r=await client.get(f"{url.rstrip('/')}/rest/v1/{table}?select=*&limit={int(limit)}",headers=headers)
    try: data=r.json()
    except Exception: data=r.text
    return {'success': 200 <= r.status_code < 300, 'table':table, 'status_code':r.status_code, 'rows':len(data) if isinstance(data,list) else 0, 'data':data if isinstance(data,list) else [], 'raw':data if not isinstance(data,list) else ''}

async def _s12_insert(table, payload):
    import os, httpx
    url=(os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL') or '').strip().strip('"').strip("'")
    key=(os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY') or '').strip().strip('"').strip("'")
    headers={'apikey':key,'Authorization':f'Bearer {key}','Accept':'application/json','Content-Type':'application/json','Prefer':'return=representation'}
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=False) as client:
        r=await client.post(f"{url.rstrip('/')}/rest/v1/{table}",headers=headers,json=payload)
    try: data=r.json()
    except Exception: data=r.text
    return {'success': 200 <= r.status_code < 300, 'table':table, 'status_code':r.status_code, 'rows':len(data) if isinstance(data,list) else 0, 'data':data if isinstance(data,list) else [], 'raw':data if not isinstance(data,list) else ''}

@app.get('/inspector', response_class=HTMLResponse)
async def inspector_page():
    content = """
<div class='card'>
<h2>Python Inspector Fix</h2>
<p>Diagnóstico isolado, sem depender dos helpers antigos que geravam Internal Server Error.</p>
<a class='btn' href='/api/inspector/python'>Python</a>
<a class='btn' href='/api/inspector/env'>Env</a>
<a class='btn' href='/api/inspector/schema'>Schema</a>
<a class='btn' href='/api/inspector/core-status'>Core Status</a>
<a class='btn' href='/api/inspector/write-log'>Teste escrita</a>
<a class='btn' href='/api/inspector/full'>Full</a>
</div>
"""
    return HTMLResponse(shell('Python Inspector', content))

@app.get('/api/inspector/python')
async def inspector_python():
    async def run():
        import sys, os, importlib.util
        return {'success': True, 'version': APP_VERSION, 'python': sys.version, 'cwd': os.getcwd(), 'modules': {'httpx': importlib.util.find_spec('httpx') is not None, 'fastapi': importlib.util.find_spec('fastapi') is not None}, 'globals': {'APP_VERSION': 'APP_VERSION' in globals(), 'db_select': 'db_select' in globals(), 'db_insert': 'db_insert' in globals(), 'DEFAULT_COMPANY_ID': 'DEFAULT_COMPANY_ID' in globals(), 'shell': 'shell' in globals()}}
    return await _s12_safe('/api/inspector/python', run)

@app.get('/api/inspector/env')
async def inspector_env():
    async def run():
        import os
        return {'success': True, 'version': APP_VERSION, 'SUPABASE_URL': _s12_mask(os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')), 'SUPABASE_SERVICE_ROLE_KEY': _s12_mask(os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')), 'SUPABASE_ANON_KEY': _s12_mask(os.getenv('SUPABASE_ANON_KEY') or os.getenv('NEXT_PUBLIC_SUPABASE_ANON_KEY'))}
    return await _s12_safe('/api/inspector/env', run)

@app.get('/api/inspector/schema')
async def inspector_schema():
    async def run():
        tables=['companies','users_app','suppliers','products','inventory','logs','marketplace_accounts','oauth_tokens','listings','orders']
        results={}; ok=0
        for t in tables:
            r=await _s12_select(t,1)
            results[t]={'success':r.get('success'),'status_code':r.get('status_code'),'rows':r.get('rows'),'raw':str(r.get('raw',''))[:500]}
            ok += 1 if r.get('success') else 0
        return {'success': ok==len(tables), 'version':APP_VERSION, 'ok_count':ok, 'total':len(tables), 'missing_or_error':[t for t,r in results.items() if not r.get('success')], 'results':results}
    return await _s12_safe('/api/inspector/schema', run)

@app.get('/api/inspector/core-status')
async def inspector_core_status():
    async def run():
        tables=['companies','users_app','suppliers','products','inventory','logs','marketplace_accounts','oauth_tokens','listings','orders']
        counts={}; ok=True
        for t in tables:
            r=await _s12_select(t,1000)
            counts[t]={'success':r.get('success'),'status_code':r.get('status_code'),'rows':r.get('rows'),'error':str(r.get('raw',''))[:500]}
            if not r.get('success'): ok=False
        return {'success': ok, 'version':APP_VERSION, 'core_ready':ok, 'counts':counts, 'next':'/dashboard' if ok else '/database-sql'}
    return await _s12_safe('/api/inspector/core-status', run)

@app.get('/api/inspector/write-log')
async def inspector_write_log():
    async def run():
        import time
        payload={'company_id':'00000000-0000-0000-0000-000000000001','event_type':'inspector_write_log','level':'info','message':f'Teste Sprint 12 {int(time.time())}','payload':{'version':APP_VERSION}}
        write=await _s12_insert('logs',payload)
        read=await _s12_select('logs',5)
        return {'success': bool(write.get('success')), 'version':APP_VERSION, 'write': {'success':write.get('success'), 'status_code':write.get('status_code'), 'rows':write.get('rows'), 'raw':str(write.get('raw',''))[:500], 'data':write.get('data',[])[:1]}, 'read_after': {'success':read.get('success'), 'status_code':read.get('status_code'), 'rows':read.get('rows'), 'raw':str(read.get('raw',''))[:500]}}
    return await _s12_safe('/api/inspector/write-log', run)

@app.get('/api/inspector/full')
async def inspector_full():
    async def run():
        py=await inspector_python(); env=await inspector_env(); schema=await inspector_schema(); core=await inspector_core_status(); write=await inspector_write_log()
        return {'success': bool(schema.get('success')) and bool(write.get('success')), 'version':APP_VERSION, 'python':py, 'env':env, 'schema':schema, 'core':core, 'write':write, 'diagnosis':'OK: banco pronto e escrita funcionando' if bool(schema.get('success')) and bool(write.get('success')) else 'Ainda há tabelas ausentes ou erro de escrita. Execute o SQL de /database-sql no Supabase.'}
    return await _s12_safe('/api/inspector/full', run)

# Aliases seguros para botões/rotas antigas de debug
@app.get('/api/debug/core-status-v2')
async def debug_core_status_v2():
    return await inspector_core_status()

@app.get('/api/debug/schema-check-v2')
async def debug_schema_check_v2():
    return await inspector_schema()




# ==========================================================
# SPRINT 13 - CONTINUITY STABLE LAYER
# Camada independente para continuidade do sistema.
# Não depende dos endpoints quebrados anteriores.
# ==========================================================

import os as _s13_os
import time as _s13_time
import uuid as _s13_uuid
import traceback as _s13_traceback

S13_VERSION = "enterprise-v5-sprint33-1-gtin-routing-hotfix"
S13_COMPANY_ID = "00000000-0000-0000-0000-000000000001"

def _s13_env(name, default=""):
    value = _s13_os.getenv(name, default)
    if value is None:
        return ""
    value = str(value).strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()
    return value

def _s13_supabase_url():
    return (_s13_env("SUPABASE_URL") or _s13_env("NEXT_PUBLIC_SUPABASE_URL")).rstrip("/")

def _s13_service_key():
    return _s13_env("SUPABASE_SERVICE_ROLE_KEY") or _s13_env("SUPABASE_KEY") or _s13_env("SUPABASE_ANON_KEY") or _s13_env("NEXT_PUBLIC_SUPABASE_ANON_KEY")

def _s13_headers():
    key = _s13_service_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def _s13_mask(value):
    value = str(value or "").strip()
    if not value:
        return {"present": False, "length": 0, "preview": ""}
    return {"present": True, "length": len(value), "preview": value[:10] + "..." + value[-6:]}

def _s13_response_error(exc, path=""):
    return {
        "success": False,
        "version": S13_VERSION,
        "error_type": type(exc).__name__,
        "message": str(exc),
        "path": path,
        "traceback": _s13_traceback.format_exc()[-8000:]
    }

async def _s13_request(method, table, query="", payload=None):
    import httpx
    url = _s13_supabase_url()
    if not url:
        return {"success": False, "status_code": 0, "error": "SUPABASE_URL ausente", "data": []}
    key = _s13_service_key()
    if not key:
        return {"success": False, "status_code": 0, "error": "SUPABASE_SERVICE_ROLE_KEY ausente", "data": []}

    endpoint = f"{url}/rest/v1/{table}"
    if query:
        endpoint += "?" + query.lstrip("?")

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        r = await client.request(method, endpoint, headers=_s13_headers(), json=payload)

    try:
        body = r.json()
    except Exception:
        body = r.text

    return {
        "success": 200 <= r.status_code < 300,
        "status_code": r.status_code,
        "table": table,
        "rows": len(body) if isinstance(body, list) else 0,
        "data": body if isinstance(body, list) else [],
        "raw": body if not isinstance(body, list) else "",
        "url": endpoint.replace(_s13_service_key(), "***")
    }

async def _s13_select(table, limit=100, order="created_at.desc"):
    return await _s13_request("GET", table, f"select=*&order={order}&limit={int(limit)}")

async def _s13_insert(table, payload):
    return await _s13_request("POST", table, "", payload)

async def _s13_patch(table, query, payload):
    return await _s13_request("PATCH", table, query, payload)

async def _s13_delete(table, query):
    return await _s13_request("DELETE", table, query)

def _s13_money(value):
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def _s13_html_table(headers, rows):
    th = "".join(f"<th>{h}</th>" for h in headers)
    if not rows:
        body = f"<tr><td colspan='{len(headers)}'>Nenhum registro encontrado.</td></tr>"
    else:
        body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"

@app.get("/continuity", response_class=HTMLResponse)
async def s13_continuity_page():
    content = """
<div class='card'>
<h2>CommerceHub Continuidade</h2>
<p>Camada estável para seguir o desenvolvimento sem depender das rotas antigas que quebraram.</p>
<a class='btn' href='/api/continuity/health'>Health Continuidade</a>
<a class='btn' href='/api/continuity/env'>Env</a>
<a class='btn' href='/api/continuity/schema'>Schema</a>
<a class='btn' href='/api/continuity/seed'>Seed</a>
<a class='btn' href='/api/continuity/status'>Status</a>
<a class='btn' href='/continuity/products'>Produtos</a>
<a class='btn' href='/continuity/suppliers'>Fornecedores</a>
<a class='btn' href='/continuity/inventory'>Estoque</a>
<a class='btn' href='/continuity/logs'>Logs</a>
</div>
"""
    return HTMLResponse(shell("CommerceHub Continuidade", content))

@app.get("/api/continuity/health")
async def s13_continuity_health():
    return {
        "status": "ok",
        "service": "commercehub",
        "version": S13_VERSION,
        "mode": "supabase",
        "supabase_configured": bool(_s13_supabase_url() and _s13_service_key())
    }

@app.get("/api/continuity/env")
async def s13_continuity_env():
    return {
        "success": True,
        "version": S13_VERSION,
        "SUPABASE_URL": _s13_mask(_s13_supabase_url()),
        "SUPABASE_SERVICE_ROLE_KEY": _s13_mask(_s13_service_key()),
        "SUPABASE_ANON_KEY": _s13_mask(_s13_env("SUPABASE_ANON_KEY") or _s13_env("NEXT_PUBLIC_SUPABASE_ANON_KEY")),
        "ML_CLIENT_ID": _s13_mask(_s13_env("ML_CLIENT_ID")),
        "ML_CLIENT_SECRET": _s13_mask(_s13_env("ML_CLIENT_SECRET")),
        "ML_REDIRECT_URI": _s13_mask(_s13_env("ML_REDIRECT_URI")),
    }

@app.get("/api/continuity/schema")
async def s13_continuity_schema():
    try:
        tables = ["companies","users_app","settings","suppliers","categories","brands","products","product_images","inventory","inventory_movements","marketplace_accounts","oauth_tokens","listings","orders","order_items","queue","sync_jobs","sync_logs","webhooks","ai_history","logs","audit_logs","notifications"]
        results = {}
        ok_count = 0
        for table in tables:
            res = await _s13_request("GET", table, "select=*&limit=1")
            results[table] = {"success": res["success"], "status_code": res["status_code"], "rows": res["rows"], "raw": str(res["raw"])[:400]}
            ok_count += 1 if res["success"] else 0
        return {
            "success": ok_count == len(tables),
            "version": S13_VERSION,
            "ok_count": ok_count,
            "total": len(tables),
            "missing_or_error": [t for t, r in results.items() if not r["success"]],
            "results": results,
            "next": "Execute /database-sql no Supabase SQL Editor se houver tabelas ausentes."
        }
    except Exception as exc:
        return _s13_response_error(exc, "/api/continuity/schema")

@app.get("/api/continuity/seed")
async def s13_continuity_seed():
    try:
        company = {
            "id": S13_COMPANY_ID,
            "name": "CommerceHub Demo",
            "legal_name": "CommerceHub Demo LTDA",
            "document": "00000000000000",
            "email": "admin@commercehub.local",
            "plan": "enterprise",
            "status": "active",
            "settings": {"currency": "BRL", "timezone": "America/Sao_Paulo"}
        }
        supplier = {
            "id": "00000000-0000-0000-0000-000000000101",
            "company_id": S13_COMPANY_ID,
            "name": "Fornecedor Manual",
            "type": "manual",
            "status": "active",
            "config": {"source": "continuity_seed"}
        }
        product = {
            "id": "00000000-0000-0000-0000-000000000401",
            "company_id": S13_COMPANY_ID,
            "supplier_id": "00000000-0000-0000-0000-000000000101",
            "sku": "CH-TEST-001",
            "name": "Produto Teste CommerceHub",
            "brand": "CommerceHub",
            "ean": "7890000000000",
            "description": "Produto criado para teste real do CommerceHub.",
            "cost_price": 25.00,
            "sale_price": 59.90,
            "status": "active",
            "raw_data": {"source": "continuity_seed"}
        }
        inventory = {
            "company_id": S13_COMPANY_ID,
            "product_id": "00000000-0000-0000-0000-000000000401",
            "sku": "CH-TEST-001",
            "quantity": 10,
            "reserved": 0,
            "status": "available"
        }
        log = {
            "company_id": S13_COMPANY_ID,
            "event_type": "continuity_seed",
            "level": "info",
            "message": "Seed executado pela Sprint 13",
            "payload": {"version": S13_VERSION}
        }

        results = {
            "company": await _s13_request("POST", "companies", "on_conflict=id", company),
            "supplier": await _s13_request("POST", "suppliers", "on_conflict=id", supplier),
            "product": await _s13_request("POST", "products", "on_conflict=id", product),
            "inventory": await _s13_insert("inventory", inventory),
            "log": await _s13_insert("logs", log),
        }
        return {"success": True, "version": S13_VERSION, "results": results, "next": "/api/continuity/status"}
    except Exception as exc:
        return _s13_response_error(exc, "/api/continuity/seed")

@app.get("/api/continuity/status")
async def s13_continuity_status():
    try:
        tables = ["companies","users_app","suppliers","products","inventory","logs","marketplace_accounts","oauth_tokens","listings","orders"]
        counts = {}
        ok = True
        for table in tables:
            res = await _s13_select(table, 1000)
            counts[table] = {"success": res["success"], "status_code": res["status_code"], "rows": res["rows"], "raw": str(res["raw"])[:300]}
            if not res["success"]:
                ok = False
        return {"success": ok, "version": S13_VERSION, "core_ready": ok, "counts": counts}
    except Exception as exc:
        return _s13_response_error(exc, "/api/continuity/status")

@app.get("/api/continuity/create-product")
async def s13_create_product():
    try:
        sku = f"CH-AUTO-{int(_s13_time.time())}"
        payload = {
            "company_id": S13_COMPANY_ID,
            "sku": sku,
            "name": f"Produto Automático {sku}",
            "brand": "CommerceHub",
            "description": "Produto criado para validar continuidade do sistema.",
            "cost_price": 35.50,
            "sale_price": 89.90,
            "status": "active",
            "raw_data": {"source": "sprint13"}
        }
        created = await _s13_insert("products", payload)
        product_id = created["data"][0]["id"] if created.get("data") else None
        inv = None
        if product_id:
            inv = await _s13_insert("inventory", {"company_id": S13_COMPANY_ID, "product_id": product_id, "sku": sku, "quantity": 5, "reserved": 0, "status": "available"})
        await _s13_insert("logs", {"company_id": S13_COMPANY_ID, "event_type": "product_created", "level": "info", "message": f"Produto {sku} criado", "payload": {"sku": sku}})
        return {"success": created["success"], "version": S13_VERSION, "sku": sku, "created": created, "inventory": inv}
    except Exception as exc:
        return _s13_response_error(exc, "/api/continuity/create-product")

@app.get("/continuity/products", response_class=HTMLResponse)
async def s13_products_page():
    res = await _s13_select("products", 100)
    rows = res.get("data", []) if res.get("success") else []
    table = _s13_html_table(["SKU","Produto","Marca","Custo","Venda","Status"], [[r.get("sku",""), r.get("name",""), r.get("brand",""), _s13_money(r.get("cost_price",0)), _s13_money(r.get("sale_price",0)), r.get("status","")] for r in rows])
    content = f"<div class='card'><h2>Produtos</h2>{table}<a class='btn' href='/api/continuity/create-product'>Criar produto teste</a></div>"
    return HTMLResponse(shell("Produtos", content))

@app.get("/continuity/suppliers", response_class=HTMLResponse)
async def s13_suppliers_page():
    res = await _s13_select("suppliers", 100)
    rows = res.get("data", []) if res.get("success") else []
    table = _s13_html_table(["Nome","Tipo","Status"], [[r.get("name",""), r.get("type",""), r.get("status","")] for r in rows])
    return HTMLResponse(shell("Fornecedores", f"<div class='card'><h2>Fornecedores</h2>{table}</div>"))

@app.get("/continuity/inventory", response_class=HTMLResponse)
async def s13_inventory_page():
    res = await _s13_select("inventory", 100)
    rows = res.get("data", []) if res.get("success") else []
    table = _s13_html_table(["SKU","Qtd","Reservado","Disponível","Status"], [[r.get("sku",""), r.get("quantity",""), r.get("reserved",""), r.get("available",""), r.get("status","")] for r in rows])
    return HTMLResponse(shell("Estoque", f"<div class='card'><h2>Estoque</h2>{table}</div>"))

@app.get("/continuity/logs", response_class=HTMLResponse)
async def s13_logs_page():
    res = await _s13_select("logs", 50)
    rows = res.get("data", []) if res.get("success") else []
    table = _s13_html_table(["Data","Tipo","Nível","Mensagem"], [[r.get("created_at",""), r.get("event_type",""), r.get("level",""), r.get("message","")] for r in rows])
    return HTMLResponse(shell("Logs", f"<div class='card'><h2>Logs</h2>{table}</div>"))

@app.get("/api/continuity/ml-readiness")
async def s13_ml_readiness():
    return {
        "success": True,
        "version": S13_VERSION,
        "mercado_livre": {
            "client_id": bool(_s13_env("ML_CLIENT_ID")),
            "client_secret": bool(_s13_env("ML_CLIENT_SECRET")),
            "redirect_uri": bool(_s13_env("ML_REDIRECT_URI")),
            "access_token": bool(_s13_env("ML_ACCESS_TOKEN")),
            "refresh_token": bool(_s13_env("ML_REFRESH_TOKEN")),
            "user_id": bool(_s13_env("ML_USER_ID")),
        },
        "next": "OAuth Mercado Livre" if bool(_s13_env("ML_CLIENT_ID") and _s13_env("ML_CLIENT_SECRET") and _s13_env("ML_REDIRECT_URI")) else "Configurar variáveis ML_CLIENT_ID, ML_CLIENT_SECRET e ML_REDIRECT_URI"
    }




# ==========================================================
# SPRINT 14 - DATABASE INSTALLER / BOOTSTRAP
# ==========================================================

EXPECTED_TABLES_S14 = [
    "companies", "users_app", "settings", "suppliers", "categories", "brands",
    "products", "product_images", "inventory", "inventory_movements",
    "marketplace_accounts", "oauth_tokens", "listings", "orders", "order_items",
    "queue", "sync_jobs", "sync_logs", "webhooks", "ai_history", "logs",
    "audit_logs", "notifications"
]

def _s14_load_schema():
    try:
        with open("commercehub_enterprise_schema.sql", "r", encoding="utf-8") as fh:
            return fh.read()
    except Exception as exc:
        return f"-- Não foi possível carregar o SQL: {exc}"

@app.get("/install", response_class=HTMLResponse)
async def install_page():
    status = await install_status()
    summary = status.get("summary", {})
    ok_count = summary.get("ok_count", 0)
    total = summary.get("total", len(EXPECTED_TABLES_S14))
    ready = summary.get("database_ready", False)
    state_label = "PRONTO" if ready else "PENDENTE"
    state_class = "ok" if ready else "bad"
    content = f"""
<div class='card'>
<h2>Instalador do Banco CommerceHub</h2>
<p>Estado atual: <b class='{state_class}'>{state_label}</b> — {ok_count}/{total} tabelas encontradas.</p>
<p>As variáveis e a conexão com o Supabase já funcionam. O passo pendente é criar o schema dentro do Supabase SQL Editor.</p>
<a class='btn' href='/install/sql'>Abrir SQL completo</a>
<a class='btn' href='/api/install/status'>Ver status JSON</a>
<a class='btn' href='/api/install/seed'>Criar dados iniciais</a>
<a class='btn' href='/continuity'>Voltar à Continuidade</a>
</div>
<div class='card'>
<h2>Como instalar</h2>
<ol>
<li>Abra <b>Supabase → SQL Editor → New query</b>.</li>
<li>Abra <b>/install/sql</b> neste sistema.</li>
<li>Copie todo o SQL e cole no SQL Editor.</li>
<li>Clique em <b>Run</b>.</li>
<li>Volte aqui e clique em <b>Ver status JSON</b>.</li>
<li>Quando aparecer 23/23, clique em <b>Criar dados iniciais</b>.</li>
</ol>
</div>
"""
    return HTMLResponse(shell("Instalador do Banco", content))

@app.get("/install/sql", response_class=HTMLResponse)
def install_sql_page():
    import html
    sql = _s14_load_schema()
    content = f"""
<div class='card'>
<h2>SQL completo do CommerceHub</h2>
<p>Use Ctrl+A e Ctrl+C dentro do bloco abaixo. Depois cole no Supabase SQL Editor e execute.</p>
<pre>{html.escape(sql)}</pre>
</div>
"""
    return HTMLResponse(shell("SQL do Banco", content))

@app.get("/api/install/status")
async def install_status():
    results = {}
    ok_count = 0
    for table in EXPECTED_TABLES_S14:
        try:
            res = await store.select(table, "select=*&limit=1")
            ok = bool(res.get("success"))
            if ok:
                ok_count += 1
            results[table] = {
                "success": ok,
                "status_code": res.get("status_code"),
                "rows": len(res.get("data", []) if isinstance(res.get("data"), list) else []),
                "error": str(res.get("error", ""))[:350],
                "raw": str(res.get("raw", ""))[:350],
            }
        except Exception as exc:
            results[table] = {"success": False, "error": str(exc)[:350]}
    ready = ok_count == len(EXPECTED_TABLES_S14)
    return {
        "success": True,
        "version": APP_VERSION,
        "summary": {
            "database_ready": ready,
            "ok_count": ok_count,
            "total": len(EXPECTED_TABLES_S14),
            "supabase_configured": store.configured(),
            "mode": store.mode(),
        },
        "missing_tables": [name for name, item in results.items() if not item.get("success")],
        "results": results,
        "next_step": "/api/install/seed" if ready else "Execute o SQL de /install/sql no Supabase SQL Editor."
    }

@app.get("/api/install/seed")
@app.post("/api/install/seed")
async def install_seed():
    check = await install_status()
    if not check.get("summary", {}).get("database_ready"):
        return {
            "success": False,
            "version": APP_VERSION,
            "error": "O schema ainda não está instalado.",
            "missing_tables": check.get("missing_tables", []),
            "next_step": "/install/sql"
        }
    import uuid, hashlib
    company = {
        "id": DEFAULT_COMPANY_ID,
        "name": "CommerceHub",
        "legal_name": "CommerceHub",
        "document": "00000000000000",
        "email": "admin@commercehub.local",
        "plan": "enterprise",
        "status": "active",
        "settings": {"currency": "BRL", "timezone": "America/Sao_Paulo"}
    }
    user = {
        "id": str(uuid.uuid4()),
        "company_id": DEFAULT_COMPANY_ID,
        "name": "Administrador",
        "email": "admin@commercehub.local",
        "role": "admin",
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
        "status": "active"
    }
    supplier = {
        "id": "00000000-0000-0000-0000-000000000101",
        "company_id": DEFAULT_COMPANY_ID,
        "name": "Fornecedor Inicial",
        "type": "manual",
        "status": "active",
        "config": {"source": "sprint14_seed"}
    }
    brand = {
        "id": "00000000-0000-0000-0000-000000000201",
        "company_id": DEFAULT_COMPANY_ID,
        "name": "CommerceHub",
        "status": "active"
    }
    category = {
        "id": "00000000-0000-0000-0000-000000000301",
        "company_id": DEFAULT_COMPANY_ID,
        "name": "Categoria Inicial",
        "marketplace": "mercadolivre",
        "status": "active"
    }
    product = {
        "id": "00000000-0000-0000-0000-000000000401",
        "company_id": DEFAULT_COMPANY_ID,
        "supplier_id": supplier["id"],
        "category_id": category["id"],
        "brand_id": brand["id"],
        "sku": "CH-TEST-001",
        "name": "Produto Teste CommerceHub",
        "brand": "CommerceHub",
        "ean": "7890000000000",
        "description": "Produto inicial para validar o banco.",
        "cost_price": 25.0,
        "sale_price": 59.9,
        "status": "active",
        "raw_data": {"source": "sprint14_seed"}
    }
    inventory = {
        "company_id": DEFAULT_COMPANY_ID,
        "product_id": product["id"],
        "sku": product["sku"],
        "quantity": 10,
        "reserved": 0,
        "status": "available"
    }
    results = {
        "company": await store.upsert("companies", company),
        "user": await store.upsert("users_app", user, "email"),
        "supplier": await store.upsert("suppliers", supplier),
        "brand": await store.upsert("brands", brand),
        "category": await store.upsert("categories", category),
        "product": await store.upsert("products", product),
        "inventory": await store.upsert("inventory", inventory, "company_id,product_id"),
        "log": await store.insert("logs", {
            "company_id": DEFAULT_COMPANY_ID,
            "event_type": "database_installed",
            "level": "info",
            "message": "Banco CommerceHub instalado e populado",
            "payload": {"version": APP_VERSION}
        })
    }
    all_ok = all(bool(item.get("success")) for item in results.values())
    return {
        "success": all_ok,
        "version": APP_VERSION,
        "results": results,
        "login": {"email": "admin@commercehub.local", "password": "admin123"},
        "next_step": "/api/continuity/status" if all_ok else "Verifique o item que retornou success=false."
    }

@app.get("/api/install/verify")
async def install_verify():
    status = await install_status()
    if not status.get("summary", {}).get("database_ready"):
        return {"success": False, "version": APP_VERSION, "stage": "schema", "details": status}
    checks = {}
    for table in ["companies", "users_app", "suppliers", "products", "inventory", "logs"]:
        res = await store.select(table, "select=*&limit=5")
        checks[table] = {
            "success": bool(res.get("success")),
            "rows": len(res.get("data", []) if isinstance(res.get("data"), list) else []),
            "status_code": res.get("status_code"),
            "error": str(res.get("error", ""))[:300]
        }
    ready = all(item.get("success") and item.get("rows", 0) >= 1 for item in checks.values())
    return {
        "success": ready,
        "version": APP_VERSION,
        "stage": "complete" if ready else "seed",
        "checks": checks,
        "next_step": "/" if ready else "/api/install/seed"
    }


# =========================
# SPRINT 15 - CORE ROUTES FIX
# =========================

@app.get("/api/core/routes-check")
async def core_routes_check():
    tables = ["companies", "users_app", "suppliers", "products", "inventory", "logs"]
    results = {}
    all_ok = True

    for table in tables:
        result = await store.select(table, "select=*&limit=5")
        item = {
            "success": bool(result.get("success")),
            "status_code": result.get("status_code"),
            "rows": len(result.get("data") or []),
            "error": str(result.get("error") or "")[:500],
        }
        results[table] = item
        if not item["success"]:
            all_ok = False

    return {
        "success": all_ok,
        "version": APP_VERSION,
        "diagnosis": "Rotas principais e Supabase operacionais." if all_ok else "Existe falha em uma ou mais tabelas.",
        "results": results,
        "pages": ["/companies", "/users", "/suppliers", "/products", "/inventory", "/logs"]
    }


# ==========================================================
# SPRINT 16 - ENTERPRISE AUTH
# JWT HS256, cookie HttpOnly, sessão, papéis e proteção de rotas.
# ==========================================================

from api.core.config import SESSION_SECRET, AUTH_REQUIRED, SESSION_HOURS, COOKIE_SECURE

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)

def create_session_token(user: dict) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user.get("id") or ""),
        "company_id": str(user.get("company_id") or DEFAULT_COMPANY_ID),
        "name": str(user.get("name") or ""),
        "email": str(user.get("email") or ""),
        "role": str(user.get("role") or "viewer"),
        "iat": now,
        "exp": now + (SESSION_HOURS * 3600),
        "jti": str(uuid.uuid4()),
    }
    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    message = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(SESSION_SECRET.encode("utf-8"), message, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64url_encode(signature)}"

def decode_session_token(token: str):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        message = f"{parts[0]}.{parts[1]}".encode("ascii")
        expected = hmac.new(SESSION_SECRET.encode("utf-8"), message, hashlib.sha256).digest()
        supplied = _b64url_decode(parts[2])
        if not hmac.compare_digest(expected, supplied):
            return None
        payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
        if int(payload.get("exp") or 0) <= int(time.time()):
            return None
        return payload
    except Exception:
        return None

def auth_user_from_request(request: Request):
    token = request.cookies.get("commercehub_session", "")
    return decode_session_token(token) if token else None

PUBLIC_PATHS = {
    "/login",
    "/api/login",
    "/api/health",
    "/api/routes",
    "/favicon.ico",
    "/install",
    "/install/sql",
    "/api/install/status",
    "/api/install/verify",
    "/api/install/seed",
}

PUBLIC_PREFIXES = (
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/audit",
    "/api/test",
    "/api/infra",
    "/api/connectivity",
    "/api/vercel",
    "/api/env-finder",
    "/api/raw",
    "/api/environment",
)

@app.middleware("http")
async def enterprise_auth_middleware(request: Request, call_next):
    path = request.url.path

    if not AUTH_REQUIRED:
        return await call_next(request)

    if path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
        return await call_next(request)

    user = auth_user_from_request(request)
    if user:
        request.state.user = user
        return await call_next(request)

    if path.startswith("/api/"):
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": "Não autenticado",
                "login_url": "/login",
                "version": APP_VERSION
            }
        )

    return RedirectResponse("/login", status_code=303)


# ==========================================================
# SPRINT 17 - UNIVERSAL SUPPLIER CONNECTOR
# Referência Hayamax + JSON, XML e CSV.
# ==========================================================

S17_HAYAMAX_SUPPLIER_ID = "00000000-0000-0000-0000-000000001700"

S17_DEMO_PRODUCTS = [
    {
        "codigo": "HAYA-1001",
        "sku": "HAYA-1001",
        "ean": "7891000001001",
        "nome": "Mouse Gamer RGB USB",
        "marca": "Fortrek",
        "categoria": "Mouse",
        "descricao": "Mouse gamer RGB com conexão USB.",
        "preco": 42.90,
        "estoque": 18,
        "imagem": "https://example.com/mouse-gamer.jpg"
    },
    {
        "codigo": "HAYA-1002",
        "sku": "HAYA-1002",
        "ean": "7891000001002",
        "nome": "Teclado Mecânico Gamer ABNT2",
        "marca": "Fortrek",
        "categoria": "Teclado",
        "descricao": "Teclado mecânico gamer padrão ABNT2.",
        "preco": 129.50,
        "estoque": 9,
        "imagem": "https://example.com/teclado-gamer.jpg"
    },
    {
        "codigo": "HAYA-1003",
        "sku": "HAYA-1003",
        "ean": "7891000001003",
        "nome": "Headset Gamer USB 7.1",
        "marca": "Harmonics",
        "categoria": "Headset",
        "descricao": "Headset gamer USB com som virtual 7.1.",
        "preco": 87.40,
        "estoque": 12,
        "imagem": "https://example.com/headset-gamer.jpg"
    }
]


def s17_escape(value):
    value = str(value if value is not None else "")
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def s17_number(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = str(value).strip().replace("R$", "").replace(" ", "")
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        return float(cleaned)
    except Exception:
        return default


def s17_integer(value, default=0):
    try:
        return int(float(str(value or default).replace(",", ".")))
    except Exception:
        return default


def s17_pick(item, aliases, default=""):
    if not isinstance(item, dict):
        return default
    lower = {str(k).lower().strip(): v for k, v in item.items()}
    for alias in aliases:
        if alias in item and item.get(alias) not in [None, ""]:
            return item.get(alias)
        value = lower.get(str(alias).lower().strip())
        if value not in [None, ""]:
            return value
    return default


def s17_normalize_product(item, supplier_id, source_format="json"):
    external_id = str(s17_pick(item, [
        "external_id", "id", "codigo", "código", "cod", "product_id",
        "idproduto", "codigo_produto", "referencia"
    ])).strip()

    sku = str(s17_pick(item, [
        "sku", "codigo", "código", "cod", "referencia", "ref", "part_number"
    ], external_id)).strip()

    ean = str(s17_pick(item, [
        "ean", "gtin", "barcode", "codigo_barras", "código_barras"
    ])).strip()

    name = str(s17_pick(item, [
        "name", "nome", "title", "titulo", "título", "produto", "descricao_curta"
    ])).strip()

    if not external_id:
        external_id = sku or ean or hashlib.sha256(
            json.dumps(item, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:24]

    if not sku:
        sku = external_id

    if not name:
        name = f"Produto {sku}"

    brand = str(s17_pick(item, ["brand", "marca", "fabricante"])).strip()
    category = str(s17_pick(item, ["category", "categoria", "departamento", "grupo"])).strip()
    description = str(s17_pick(item, [
        "description", "descricao", "descrição", "descricao_longa", "detalhes"
    ])).strip()

    cost_price = s17_number(s17_pick(item, [
        "cost_price", "preco_custo", "preço_custo", "preco", "preço",
        "price", "valor", "valor_unitario"
    ], 0))

    sale_price = s17_number(s17_pick(item, [
        "sale_price", "preco_venda", "preço_venda", "suggested_price",
        "preco_sugerido"
    ], 0))

    if sale_price <= 0 and cost_price > 0:
        sale_price = round(cost_price * 1.35, 2)

    stock = s17_integer(s17_pick(item, [
        "stock", "estoque", "quantity", "quantidade", "saldo", "disponivel"
    ], 0))

    image_url = str(s17_pick(item, [
        "image_url", "imagem", "image", "foto", "url_imagem", "imagem_principal"
    ])).strip()

    status_value = str(s17_pick(item, ["status", "situacao", "situação"], "active")).lower()
    status = "inactive" if status_value in ["inactive", "inativo", "0", "false", "indisponivel"] else "active"

    return {
        "company_id": DEFAULT_COMPANY_ID,
        "supplier_id": supplier_id,
        "external_id": external_id,
        "sku": sku,
        "ean": ean or None,
        "name": name,
        "brand": brand or None,
        "category": category or None,
        "description": description or None,
        "cost_price": cost_price,
        "sale_price": sale_price,
        "stock": stock,
        "image_url": image_url or None,
        "status": status,
        "source_format": source_format,
        "raw_data": item,
    }


def s17_xml_node_to_dict(node):
    result = {}
    for child in list(node):
        if len(list(child)) > 0:
            result[child.tag.split("}")[-1]] = s17_xml_node_to_dict(child)
        else:
            result[child.tag.split("}")[-1]] = (child.text or "").strip()
    result.update({k.split("}")[-1]: v for k, v in node.attrib.items()})
    return result


def s17_parse_payload(raw_text, source_format):
    fmt = str(source_format or "").lower().strip()
    raw_text = str(raw_text or "").strip()

    if fmt == "json":
        parsed = json.loads(raw_text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for key in ["products", "produtos", "items", "itens", "data", "catalog"]:
                value = parsed.get(key)
                if isinstance(value, list):
                    return value
            return [parsed]
        return []

    if fmt == "csv":
        sample = raw_text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except Exception:
            dialect = csv.excel
            dialect.delimiter = ";"
        return list(csv.DictReader(io.StringIO(raw_text), dialect=dialect))

    if fmt == "xml":
        root = ET.fromstring(raw_text)
        candidates = []
        common_tags = {"produto", "product", "item", "registro"}
        for node in root.iter():
            tag = node.tag.split("}")[-1].lower()
            if tag in common_tags and len(list(node)) > 0:
                candidates.append(s17_xml_node_to_dict(node))
        if candidates:
            return candidates

        children = list(root)
        if children:
            return [s17_xml_node_to_dict(node) for node in children]
        return [s17_xml_node_to_dict(root)]

    raise ValueError("Formato não suportado. Use json, xml ou csv.")


async def s17_get_supplier(supplier_id):
    result = await store.select(
        "suppliers",
        f"select=*&id=eq.{quote(str(supplier_id), safe='-')}&limit=1"
    )
    rows = result.get("data") or []
    return rows[0] if rows else None


async def s17_ensure_hayamax_supplier():
    current = await s17_get_supplier(S17_HAYAMAX_SUPPLIER_ID)
    payload = {
        "id": S17_HAYAMAX_SUPPLIER_ID,
        "company_id": DEFAULT_COMPANY_ID,
        "name": "Hayamax",
        "document": "01725627000172",
        "email": "hayamax@hayamax.com.br",
        "phone": "(43) 3377-6600",
        "type": "xml",
        "status": "active",
        "config": {
            "connector": "universal_supplier_v1",
            "reference_supplier": "hayamax",
            "source_format": "xml",
            "catalog_url": "",
            "authentication": "provided_by_supplier_or_partner",
            "note": "Preencha a URL oficial disponibilizada ao revendedor."
        }
    }
    if current:
        payload["created_at"] = current.get("created_at")
    return await store.upsert("suppliers", payload, "id")


async def s17_create_job(supplier_id, mode):
    job_id = str(uuid.uuid4())
    now = __import__("datetime").datetime.utcnow().isoformat()
    payload = {
        "id": job_id,
        "company_id": DEFAULT_COMPANY_ID,
        "sync_type": "supplier_catalog_import",
        "marketplace": None,
        "status": "running",
        "payload": {"supplier_id": supplier_id, "mode": mode, "version": APP_VERSION},
        "result": {},
        "started_at": now
    }
    await store.upsert("sync_jobs", payload, "id")
    return payload


async def s17_finish_job(job, status, result):
    job["status"] = status
    job["result"] = result
    job["finished_at"] = __import__("datetime").datetime.utcnow().isoformat()
    return await store.upsert("sync_jobs", job, "id")


async def s17_job_log(job_id, level, message, payload=None):
    return await store.insert("sync_logs", {
        "company_id": DEFAULT_COMPANY_ID,
        "sync_job_id": job_id,
        "level": level,
        "message": message,
        "payload": payload or {}
    })


async def s17_import_normalized(supplier, normalized, mode="manual"):
    job = await s17_create_job(supplier["id"], mode)
    stats = {
        "received": len(normalized),
        "normalized": 0,
        "supplier_products": 0,
        "master_created_or_updated": 0,
        "inventory_created_or_updated": 0,
        "errors": []
    }

    await s17_job_log(job["id"], "info", "Importação iniciada", {
        "supplier": supplier.get("name"),
        "received": len(normalized),
        "mode": mode
    })

    for item in normalized:
        try:
            stats["normalized"] += 1
            offer = await store.upsert(
                "supplier_products",
                item,
                "company_id,supplier_id,external_id"
            )
            if not offer.get("success"):
                raise RuntimeError(str(offer.get("error") or offer.get("raw") or "Falha supplier_products"))
            stats["supplier_products"] += 1

            product_id = str(uuid.uuid5(
                uuid.UUID("00000000-0000-0000-0000-000000000017"),
                f"{DEFAULT_COMPANY_ID}:{supplier['id']}:{item['sku']}"
            ))

            product_payload = {
                "id": product_id,
                "company_id": DEFAULT_COMPANY_ID,
                "supplier_id": supplier["id"],
                "sku": item["sku"],
                "name": item["name"],
                "brand": item.get("brand"),
                "ean": item.get("ean"),
                "description": item.get("description"),
                "cost_price": item.get("cost_price", 0),
                "sale_price": item.get("sale_price", 0),
                "status": item.get("status", "active"),
                "raw_data": {
                    "source": "supplier_connector",
                    "supplier_id": supplier["id"],
                    "external_id": item["external_id"],
                    "category": item.get("category"),
                    "image_url": item.get("image_url"),
                    "source_format": item.get("source_format")
                }
            }

            master = await store.upsert("products", product_payload, "company_id,sku")
            if not master.get("success"):
                raise RuntimeError(str(master.get("error") or master.get("raw") or "Falha products"))
            stats["master_created_or_updated"] += 1

            master_rows = master.get("data") or []
            real_product_id = master_rows[0].get("id") if master_rows else product_id

            inventory_payload = {
                "company_id": DEFAULT_COMPANY_ID,
                "product_id": real_product_id,
                "sku": item["sku"],
                "quantity": item.get("stock", 0),
                "reserved": 0,
                "status": "available" if item.get("stock", 0) > 0 else "unavailable"
            }

            inventory = await store.upsert(
                "inventory",
                inventory_payload,
                "company_id,product_id"
            )
            if not inventory.get("success"):
                raise RuntimeError(str(inventory.get("error") or inventory.get("raw") or "Falha inventory"))
            stats["inventory_created_or_updated"] += 1

            await store.upsert(
                "supplier_products",
                {**item, "product_id": real_product_id},
                "company_id,supplier_id,external_id"
            )

        except Exception as exc:
            stats["errors"].append({
                "external_id": item.get("external_id"),
                "sku": item.get("sku"),
                "error": str(exc)[:500]
            })

    final_status = "completed" if not stats["errors"] else "completed_with_errors"
    await s17_finish_job(job, final_status, stats)
    await s17_job_log(job["id"], "info" if not stats["errors"] else "warning",
                      "Importação finalizada", stats)

    await store.insert("logs", {
        "company_id": DEFAULT_COMPANY_ID,
        "event_type": "supplier_catalog_import",
        "level": "info" if not stats["errors"] else "warning",
        "message": f"Catálogo de {supplier.get('name')} importado: {stats['master_created_or_updated']} produtos",
        "payload": {"job_id": job["id"], **stats}
    })

    return {
        "success": len(stats["errors"]) == 0,
        "version": APP_VERSION,
        "job_id": job["id"],
        "supplier": supplier.get("name"),
        "stats": stats
    }


@app.get("/supplier-connector", response_class=HTMLResponse)
async def supplier_connector_page(request: Request):
    suppliers_result = await store.select(
        "suppliers",
        "select=id,name,type,status,config,updated_at&order=name.asc"
    )
    suppliers = suppliers_result.get("data") or []

    rows = ""
    for supplier in suppliers:
        config = supplier.get("config") or {}
        connector = config.get("connector", "não configurado")
        source_format = config.get("source_format", supplier.get("type", "manual"))
        catalog_url = config.get("catalog_url") or ""
        rows += f"""
<tr>
<td>{s17_escape(supplier.get('name'))}</td>
<td>{s17_escape(source_format)}</td>
<td>{s17_escape(connector)}</td>
<td>{s17_escape(supplier.get('status'))}</td>
<td>{'Configurada' if catalog_url else 'Pendente'}</td>
<td>
<a class='btn' href='/supplier-connector/{supplier.get("id")}'>Configurar</a>
<a class='btn' href='/api/suppliers/{supplier.get("id")}/test'>Testar</a>
</td>
</tr>
"""

    if not rows:
        rows = "<tr><td colspan='6'>Nenhum fornecedor cadastrado.</td></tr>"

    content = f"""
<div class='card'>
<h2>Universal Supplier Connector</h2>
<p>Importa catálogos JSON, XML ou CSV, normaliza os dados e atualiza Produtos e Estoque.</p>
<a class='btn' href='/api/suppliers/hayamax/setup'>Adicionar Hayamax</a>
<a class='btn' href='/api/suppliers/hayamax/demo-import'>Importação demonstrativa Hayamax</a>
<a class='btn' href='/supplier-imports'>Histórico</a>
<a class='btn' href='/supplier-connector/sql'>SQL Sprint 17</a>
</div>
<div class='card'>
<h2>Fornecedores conectáveis</h2>
<table>
<thead><tr><th>Fornecedor</th><th>Formato</th><th>Conector</th><th>Status</th><th>URL</th><th>Ações</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>
<div class='card'>
<h2>Fluxo</h2>
<pre>Fornecedor → JSON/XML/CSV → Parser → Normalizador → Catálogo Mestre → Estoque → Mercado Livre</pre>
</div>
"""
    return HTMLResponse(shell("Supplier Connector", content))


@app.get("/supplier-connector/sql", response_class=HTMLResponse)
async def supplier_connector_sql_page():
    sql_text = open("sprint17_supplier_connector.sql", "r", encoding="utf-8").read()
    return HTMLResponse(shell(
        "SQL Sprint 17",
        f"<div class='card'><h2>Migration Supplier Connector</h2><p>Copie e execute no Supabase SQL Editor.</p><pre>{s17_escape(sql_text)}</pre></div>"
    ))


@app.get("/supplier-connector/{supplier_id}", response_class=HTMLResponse)
async def supplier_connector_config_page(supplier_id: str):
    supplier = await s17_get_supplier(supplier_id)
    if not supplier:
        return HTMLResponse(shell("Fornecedor", "<div class='card'><h2>Fornecedor não encontrado.</h2></div>"), status_code=404)

    config = supplier.get("config") or {}
    content = f"""
<div class='card'>
<h2>Configurar {s17_escape(supplier.get('name'))}</h2>
<form method='post' action='/api/suppliers/{s17_escape(supplier_id)}/config'>
<label>Formato da fonte</label>
<select name='source_format' style='width:100%;padding:10px;border:1px solid #cbd5e1;border-radius:8px;margin:5px 0 12px'>
<option value='json' {'selected' if config.get('source_format') == 'json' else ''}>JSON</option>
<option value='xml' {'selected' if config.get('source_format') == 'xml' else ''}>XML</option>
<option value='csv' {'selected' if config.get('source_format') == 'csv' else ''}>CSV</option>
</select>
<label>URL do catálogo</label>
<input name='catalog_url' value='{s17_escape(config.get("catalog_url") or "")}' placeholder='https://fornecedor.com/catalogo.xml'>
<label>Header de autenticação (nome)</label>
<input name='auth_header' value='{s17_escape(config.get("auth_header") or "")}' placeholder='Authorization ou X-API-Key'>
<label>Valor do header</label>
<input name='auth_value' type='password' value='{s17_escape(config.get("auth_value") or "")}' placeholder='Token fornecido pelo fornecedor'>
<label>Margem padrão (%)</label>
<input name='margin_percent' value='{s17_escape(config.get("margin_percent") or "35")}' placeholder='35'>
<button type='submit'>Salvar configuração</button>
</form>
</div>
<div class='card'>
<a class='btn' href='/api/suppliers/{s17_escape(supplier_id)}/test'>Testar conexão</a>
<a class='btn' href='/api/suppliers/{s17_escape(supplier_id)}/preview'>Pré-visualizar</a>
<a class='btn' href='/api/suppliers/{s17_escape(supplier_id)}/import'>Importar catálogo</a>
</div>
"""
    return HTMLResponse(shell(f"Conector - {supplier.get('name')}", content))


@app.post("/api/suppliers/{supplier_id}/config")
async def supplier_connector_save_config(supplier_id: str, request: Request):
    supplier = await s17_get_supplier(supplier_id)
    if not supplier:
        return JSONResponse(status_code=404, content={"success": False, "error": "Fornecedor não encontrado"})

    form = await request.form()
    current_config = supplier.get("config") or {}
    config = {
        **current_config,
        "connector": "universal_supplier_v1",
        "source_format": str(form.get("source_format") or "json").lower(),
        "catalog_url": str(form.get("catalog_url") or "").strip(),
        "auth_header": str(form.get("auth_header") or "").strip(),
        "auth_value": str(form.get("auth_value") or "").strip(),
        "margin_percent": s17_number(form.get("margin_percent"), 35),
    }
    payload = {**supplier, "config": config, "type": config["source_format"]}
    result = await store.upsert("suppliers", payload, "id")

    if not result.get("success"):
        return JSONResponse(status_code=400, content={
            "success": False,
            "error": result.get("error") or result.get("raw"),
            "result": result
        })
    return RedirectResponse(f"/supplier-connector/{supplier_id}", status_code=303)


@app.get("/api/suppliers/hayamax/setup")
async def supplier_hayamax_setup():
    result = await s17_ensure_hayamax_supplier()
    return {
        "success": bool(result.get("success")),
        "version": APP_VERSION,
        "supplier_id": S17_HAYAMAX_SUPPLIER_ID,
        "supplier": "Hayamax",
        "result": result,
        "next": f"/supplier-connector/{S17_HAYAMAX_SUPPLIER_ID}"
    }


@app.get("/api/suppliers/hayamax/demo-import")
async def supplier_hayamax_demo_import():
    migration_check = await store.select("supplier_products", "select=id&limit=1")
    if not migration_check.get("success"):
        return JSONResponse(status_code=409, content={
            "success": False,
            "version": APP_VERSION,
            "error": "A tabela supplier_products ainda não existe.",
            "next_step": "Execute o SQL disponível em /supplier-connector/sql no Supabase SQL Editor.",
            "details": str(migration_check.get("error") or migration_check.get("raw"))[:600]
        })

    await s17_ensure_hayamax_supplier()
    supplier = await s17_get_supplier(S17_HAYAMAX_SUPPLIER_ID)
    normalized = [
        s17_normalize_product(item, supplier["id"], "hayamax_demo")
        for item in S17_DEMO_PRODUCTS
    ]
    return await s17_import_normalized(supplier, normalized, "hayamax_demo")


async def s17_fetch_supplier_catalog(supplier):
    import httpx

    config = supplier.get("config") or {}
    catalog_url = str(config.get("catalog_url") or "").strip()
    source_format = str(config.get("source_format") or supplier.get("type") or "json").lower()

    if not catalog_url:
        return {
            "success": False,
            "error": "URL do catálogo não configurada.",
            "source_format": source_format
        }

    parsed_url = urlparse(catalog_url)
    if parsed_url.scheme not in ["http", "https"]:
        return {
            "success": False,
            "error": "A URL deve iniciar com http:// ou https://.",
            "source_format": source_format
        }

    request_headers = {"Accept": "*/*", "User-Agent": "CommerceHub-Supplier-Connector/1.0"}
    auth_header = str(config.get("auth_header") or "").strip()
    auth_value = str(config.get("auth_value") or "").strip()
    if auth_header and auth_value:
        request_headers[auth_header] = auth_value

    try:
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            response = await client.get(catalog_url, headers=request_headers)

        return {
            "success": 200 <= response.status_code < 300,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "content_length": len(response.content),
            "text": response.text,
            "source_format": source_format,
            "final_url": str(response.url),
        }
    except Exception as exc:
        return {
            "success": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "source_format": source_format
        }


@app.get("/api/suppliers/{supplier_id}/test")
async def supplier_connector_test(supplier_id: str):
    supplier = await s17_get_supplier(supplier_id)
    if not supplier:
        return JSONResponse(status_code=404, content={"success": False, "error": "Fornecedor não encontrado"})

    config = supplier.get("config") or {}
    if not config.get("catalog_url"):
        return {
            "success": False,
            "version": APP_VERSION,
            "supplier": supplier.get("name"),
            "configured": False,
            "message": "Fornecedor cadastrado, mas a URL do catálogo ainda não foi informada.",
            "next": f"/supplier-connector/{supplier_id}"
        }

    fetched = await s17_fetch_supplier_catalog(supplier)
    return {
        "success": bool(fetched.get("success")),
        "version": APP_VERSION,
        "supplier": supplier.get("name"),
        "configured": True,
        "status_code": fetched.get("status_code"),
        "content_type": fetched.get("content_type"),
        "content_length": fetched.get("content_length"),
        "final_url": fetched.get("final_url"),
        "error": fetched.get("error", "")
    }


@app.get("/api/suppliers/{supplier_id}/preview")
async def supplier_connector_preview(supplier_id: str):
    supplier = await s17_get_supplier(supplier_id)
    if not supplier:
        return JSONResponse(status_code=404, content={"success": False, "error": "Fornecedor não encontrado"})

    fetched = await s17_fetch_supplier_catalog(supplier)
    if not fetched.get("success"):
        return fetched

    try:
        items = s17_parse_payload(fetched.get("text", ""), fetched.get("source_format"))
        normalized = [
            s17_normalize_product(item, supplier["id"], fetched.get("source_format"))
            for item in items[:10]
        ]
        return {
            "success": True,
            "version": APP_VERSION,
            "supplier": supplier.get("name"),
            "source_format": fetched.get("source_format"),
            "detected_items": len(items),
            "preview_count": len(normalized),
            "preview": normalized
        }
    except Exception as exc:
        return {
            "success": False,
            "version": APP_VERSION,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "hint": "Confira o formato escolhido e a estrutura do catálogo."
        }


@app.get("/api/suppliers/{supplier_id}/import")
async def supplier_connector_import(supplier_id: str):
    supplier = await s17_get_supplier(supplier_id)
    if not supplier:
        return JSONResponse(status_code=404, content={"success": False, "error": "Fornecedor não encontrado"})

    migration_check = await store.select("supplier_products", "select=id&limit=1")
    if not migration_check.get("success"):
        return JSONResponse(status_code=409, content={
            "success": False,
            "error": "Execute primeiro a migration da Sprint 17.",
            "next": "/supplier-connector/sql"
        })

    fetched = await s17_fetch_supplier_catalog(supplier)
    if not fetched.get("success"):
        return fetched

    try:
        items = s17_parse_payload(fetched.get("text", ""), fetched.get("source_format"))
        normalized = [
            s17_normalize_product(item, supplier["id"], fetched.get("source_format"))
            for item in items
        ]
        return await s17_import_normalized(supplier, normalized, "remote_catalog")
    except Exception as exc:
        return {
            "success": False,
            "version": APP_VERSION,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "hint": "Use /api/suppliers/{id}/preview antes de importar."
        }


@app.get("/supplier-imports", response_class=HTMLResponse)
async def supplier_imports_page():
    jobs_result = await store.select(
        "sync_jobs",
        "select=*&sync_type=eq.supplier_catalog_import&order=created_at.desc&limit=50"
    )
    jobs = jobs_result.get("data") or []

    rows = ""
    for job in jobs:
        payload = job.get("payload") or {}
        result = job.get("result") or {}
        rows += f"""
<tr>
<td>{s17_escape(job.get('created_at'))}</td>
<td>{s17_escape(payload.get('mode'))}</td>
<td>{s17_escape(job.get('status'))}</td>
<td>{s17_escape(result.get('received', 0))}</td>
<td>{s17_escape(result.get('master_created_or_updated', 0))}</td>
<td>{s17_escape(len(result.get('errors') or []))}</td>
<td><a class='btn' href='/api/supplier-imports/{job.get("id")}'>Detalhes</a></td>
</tr>
"""

    if not rows:
        rows = "<tr><td colspan='7'>Nenhuma importação executada.</td></tr>"

    content = f"""
<div class='card'>
<h2>Histórico de Importações</h2>
<table>
<thead><tr><th>Data</th><th>Modo</th><th>Status</th><th>Recebidos</th><th>Catálogo mestre</th><th>Erros</th><th>Ação</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>
"""
    return HTMLResponse(shell("Importações de Fornecedores", content))


@app.get("/api/supplier-imports/{job_id}")
async def supplier_import_details(job_id: str):
    job_result = await store.select(
        "sync_jobs",
        f"select=*&id=eq.{quote(job_id, safe='-')}&limit=1"
    )
    logs_result = await store.select(
        "sync_logs",
        f"select=*&sync_job_id=eq.{quote(job_id, safe='-')}&order=created_at.asc"
    )
    jobs = job_result.get("data") or []
    return {
        "success": bool(jobs),
        "version": APP_VERSION,
        "job": jobs[0] if jobs else None,
        "logs": logs_result.get("data") or []
    }


@app.get("/api/supplier-connector/status")
async def supplier_connector_status():
    checks = {}
    for table in ["suppliers", "supplier_products", "products", "inventory", "sync_jobs", "sync_logs"]:
        result = await store.select(table, "select=*&limit=1")
        checks[table] = {
            "success": bool(result.get("success")),
            "status_code": result.get("status_code"),
            "rows": len(result.get("data") or []),
            "error": str(result.get("error") or result.get("raw") or "")[:500]
        }

    return {
        "success": all(item["success"] for item in checks.values()),
        "version": APP_VERSION,
        "module": "universal_supplier_connector",
        "formats": ["json", "xml", "csv"],
        "reference_supplier": "Hayamax",
        "checks": checks,
        "next": "/supplier-connector"
    }


# ==========================================================
# SPRINT 18 - PRODUCT MASTER
# Catálogo central para fornecedores e marketplaces.
# ==========================================================

def s18_escape(value):
    value = str(value if value is not None else "")
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def s18_money(value):
    try:
        return f"R$ {float(value or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def s18_decimal(value, default=0):
    try:
        text = str(value or "").strip().replace("R$", "").replace(" ", "")
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", ".")
        return float(text) if text else default
    except Exception:
        return default


def s18_int(value, default=0):
    try:
        return int(float(str(value or default).replace(",", ".")))
    except Exception:
        return default


async def s18_get_product(product_id):
    result = await store.select(
        "products",
        f"select=*&id=eq.{quote(str(product_id), safe='-')}&limit=1"
    )
    rows = result.get("data") or []
    return rows[0] if rows else None


async def s18_history(product_id, event_type, message, field_name=None, old_value=None, new_value=None, payload=None):
    return await store.insert("product_history", {
        "company_id": DEFAULT_COMPANY_ID,
        "product_id": product_id,
        "event_type": event_type,
        "field_name": field_name,
        "old_value": None if old_value is None else str(old_value),
        "new_value": None if new_value is None else str(new_value),
        "source": "commercehub",
        "message": message,
        "payload": payload or {}
    })


@app.get("/product-master", response_class=HTMLResponse)
async def product_master_page(request: Request):
    search = str(request.query_params.get("q") or "").strip()
    status_filter = str(request.query_params.get("status") or "").strip()
    supplier_filter = str(request.query_params.get("supplier") or "").strip()
    page = max(1, s18_int(request.query_params.get("page"), 1))
    page_size = 50
    offset = (page - 1) * page_size

    query = "select=*&company_id=eq." + quote(DEFAULT_COMPANY_ID, safe="-")
    if status_filter:
        query += "&internal_status=eq." + quote(status_filter, safe="_-")
    query += f"&order=updated_at.desc&limit={page_size}&offset={offset}"

    result = await store.select("products", query)
    products = result.get("data") or []

    if search:
        search_lower = search.lower()
        products = [
            p for p in products
            if search_lower in str(p.get("sku") or "").lower()
            or search_lower in str(p.get("ean") or "").lower()
            or search_lower in str(p.get("name") or "").lower()
            or search_lower in str(p.get("brand") or "").lower()
        ]

    suppliers_result = await store.select("suppliers", "select=id,name&order=name.asc")
    suppliers_map = {str(s.get("id")): s.get("name") for s in (suppliers_result.get("data") or [])}

    rows = ""
    for product in products:
        image = product.get("primary_image_url") or ""
        image_html = (
            f"<img src='{s18_escape(image)}' alt='' style='width:48px;height:48px;object-fit:contain;border-radius:8px'>"
            if image else
            "<div style='width:48px;height:48px;border:1px solid #d1d5db;border-radius:8px;display:grid;place-items:center'>—</div>"
        )
        supplier_name = suppliers_map.get(str(product.get("supplier_id")), "-")
        rows += f"""
<tr>
<td>{image_html}</td>
<td>{s18_escape(product.get('sku'))}</td>
<td><a href='/product-master/{product.get("id")}'>{s18_escape(product.get('name'))}</a></td>
<td>{s18_escape(product.get('brand') or '-')}</td>
<td>{s18_escape(supplier_name)}</td>
<td>{s18_money(product.get('cost_price'))}</td>
<td>{s18_money(product.get('sale_price'))}</td>
<td>{s18_escape(product.get('internal_status') or 'draft')}</td>
<td>{s18_escape(product.get('sync_status') or 'pending')}</td>
</tr>
"""
    if not rows:
        rows = "<tr><td colspan='9'>Nenhum produto encontrado.</td></tr>"


    content = f"""
<div class='grid'>
<div class='metric'><span>Produtos nesta página</span><strong>{len(products)}</strong></div>
<div class='metric'><span>Página</span><strong>{page}</strong></div>
<div class='metric'><span>Catálogo</span><strong>Master</strong></div>
<div class='metric'><span>Destino</span><strong>Marketplaces</strong></div>
</div>
<div class='card'>
<h2>Catálogo Mestre</h2>
<form method='get' action='/product-master'>
<label>Buscar por SKU, EAN, nome ou marca</label>
<input name='q' value='{s18_escape(search)}' placeholder='Ex.: HAYA-1001 ou Mouse Gamer'>
<label>Status interno</label>
<select name='status' style='width:100%;padding:10px;border:1px solid #cbd5e1;border-radius:8px;margin:5px 0 12px'>
<option value=''>Todos</option>
<option value='draft' {'selected' if status_filter == 'draft' else ''}>Draft</option>
<option value='ready' {'selected' if status_filter == 'ready' else ''}>Ready</option>
<option value='paused' {'selected' if status_filter == 'paused' else ''}>Paused</option>
<option value='archived' {'selected' if status_filter == 'archived' else ''}>Archived</option>
</select>
<button type='submit'>Buscar</button>
<a class='btn' href='/product-master/new'>Novo produto</a>
<a class='btn' href='/product-master/sql'>SQL Sprint 18</a>
<a class='btn' href='/api/product-master/status'>Status do módulo</a>
</form>
</div>
<div class='card'>
<table>
<thead><tr><th>Foto</th><th>SKU</th><th>Produto</th><th>Marca</th><th>Fornecedor</th><th>Custo</th><th>Venda</th><th>Status</th><th>Sync</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<div style='margin-top:14px'>
<a class='btn' href='/product-master?page={max(1,page-1)}&q={quote(search)}&status={quote(status_filter)}'>Anterior</a>
<a class='btn' href='/product-master?page={page+1}&q={quote(search)}&status={quote(status_filter)}'>Próxima</a>
</div>
</div>
"""
    return HTMLResponse(shell("Product Master", content))


@app.get("/product-master/sql", response_class=HTMLResponse)
async def product_master_sql_page():
    sql_text = open("sprint18_product_master.sql", "r", encoding="utf-8").read()
    return HTMLResponse(shell(
        "SQL Sprint 18",
        f"<div class='card'><h2>Migration Product Master</h2><p>Copie e execute no Supabase SQL Editor.</p><pre>{s18_escape(sql_text)}</pre></div>"
    ))


@app.get("/product-master/new", response_class=HTMLResponse)
async def product_master_new_page():
    suppliers = await store.select("suppliers", "select=id,name&order=name.asc")
    supplier_options = "<option value=''>Sem fornecedor</option>" + "".join(
        f"<option value='{s18_escape(s.get('id'))}'>{s18_escape(s.get('name'))}</option>"
        for s in (suppliers.get("data") or [])
    )
    content = f"""
<div class='card'>
<h2>Novo Produto Mestre</h2>
<form method='post' action='/api/product-master/create'>
<label>SKU interno</label><input name='sku' required>
<label>EAN/GTIN</label><input name='ean'>
<label>Nome</label><input name='name' required>
<label>Nome SEO</label><input name='seo_name'>
<label>Marca</label><input name='brand'>
<label>Fornecedor principal</label>
<select name='supplier_id' style='width:100%;padding:10px;border:1px solid #cbd5e1;border-radius:8px;margin:5px 0 12px'>{supplier_options}</select>
<label>Descrição curta</label><input name='short_description'>
<label>Descrição longa</label><textarea name='description' style='width:100%;min-height:120px;padding:10px;border:1px solid #cbd5e1;border-radius:8px'></textarea>
<label>Preço de custo</label><input name='cost_price' value='0'>
<label>Preço de venda</label><input name='sale_price' value='0'>
<label>Peso (kg)</label><input name='weight_kg' value='0'>
<label>Altura (cm)</label><input name='height_cm' value='0'>
<label>Largura (cm)</label><input name='width_cm' value='0'>
<label>Comprimento (cm)</label><input name='length_cm' value='0'>
<label>NCM</label><input name='ncm'>
<label>Garantia (meses)</label><input name='warranty_months' value='0'>
<label>Imagem principal (URL)</label><input name='primary_image_url'>
<button type='submit'>Criar produto</button>
</form>
</div>
"""
    return HTMLResponse(shell("Novo Produto Mestre", content))


@app.post("/api/product-master/create")
async def product_master_create(request: Request):
    form = await request.form()
    sku = str(form.get("sku") or "").strip()
    name = str(form.get("name") or "").strip()
    if not sku or not name:
        return JSONResponse(status_code=400, content={"success": False, "error": "SKU e nome são obrigatórios."})

    product_id = str(uuid.uuid4())
    payload = {
        "id": product_id,
        "company_id": DEFAULT_COMPANY_ID,
        "supplier_id": str(form.get("supplier_id") or "").strip() or None,
        "sku": sku,
        "ean": str(form.get("ean") or "").strip() or None,
        "name": name,
        "seo_name": str(form.get("seo_name") or "").strip() or name,
        "brand": str(form.get("brand") or "").strip() or None,
        "model": str(form.get("model") or "").strip() or None,
        "ml_category_id": str(form.get("ml_category_id") or "").strip() or None,
        "short_description": str(form.get("short_description") or "").strip() or None,
        "description": str(form.get("description") or "").strip() or None,
        "cost_price": s18_decimal(form.get("cost_price"), 0),
        "sale_price": s18_decimal(form.get("sale_price"), 0),
        "weight_kg": s18_decimal(form.get("weight_kg"), 0),
        "height_cm": s18_decimal(form.get("height_cm"), 0),
        "width_cm": s18_decimal(form.get("width_cm"), 0),
        "length_cm": s18_decimal(form.get("length_cm"), 0),
        "ncm": str(form.get("ncm") or "").strip() or None,
        "warranty_months": s18_int(form.get("warranty_months"), 0),
        "primary_image_url": str(form.get("primary_image_url") or "").strip() or None,
        "status": "active",
        "internal_status": "draft",
        "sync_status": "pending",
        "raw_data": {"source": "product_master_manual"}
    }
    created = await store.insert("products", payload)
    if not created.get("success"):
        return JSONResponse(status_code=400, content={"success": False, "error": created.get("error") or created.get("raw"), "result": created})

    await s18_history(product_id, "created", f"Produto {sku} criado manualmente", payload={"sku": sku})
    return RedirectResponse(f"/product-master/{product_id}", status_code=303)


@app.get("/product-master/{product_id}", response_class=HTMLResponse)
async def product_master_details_page(product_id: str):
    product = await s18_get_product(product_id)
    if not product:
        return HTMLResponse(shell("Produto", "<div class='card'><h2>Produto não encontrado.</h2></div>"), status_code=404)

    images_result = await store.select("product_images", f"select=*&product_id=eq.{quote(product_id, safe='-')}&order=position.asc")
    attributes_result = await store.select("product_attributes", f"select=*&product_id=eq.{quote(product_id, safe='-')}&order=name.asc")
    suppliers_result = await store.select("product_suppliers", f"select=*&product_id=eq.{quote(product_id, safe='-')}&order=priority.asc")
    history_result = await store.select("product_history", f"select=*&product_id=eq.{quote(product_id, safe='-')}&order=created_at.desc&limit=50")
    inventory_result = await store.select("inventory", f"select=*&product_id=eq.{quote(product_id, safe='-')}&limit=1")

    image_cards = ""
    for image in images_result.get("data") or []:
        image_cards += f"""
<div class='card' style='display:inline-block;width:180px;vertical-align:top;margin-right:10px'>
<img src='{s18_escape(image.get("url"))}' style='width:100%;height:130px;object-fit:contain'>
<p>Posição: {s18_escape(image.get("position"))}</p>
<p>{'Principal' if image.get('is_main') else 'Secundária'}</p>
</div>
"""
    if not image_cards:
        image_cards = "<p>Nenhuma imagem cadastrada.</p>"

    attr_rows = "".join(
        f"<tr><td>{s18_escape(a.get('name'))}</td><td>{s18_escape(a.get('value'))}</td><td>{s18_escape(a.get('unit') or '')}</td><td>{s18_escape(a.get('source'))}</td></tr>"
        for a in (attributes_result.get("data") or [])
    ) or "<tr><td colspan='4'>Nenhum atributo.</td></tr>"

    supplier_rows = "".join(
        f"<tr><td>{s18_escape(s.get('supplier_sku') or '-')}</td><td>{s18_money(s.get('cost_price'))}</td><td>{s18_escape(s.get('stock'))}</td><td>{s18_escape(s.get('priority'))}</td><td>{'Sim' if s.get('is_preferred') else 'Não'}</td></tr>"
        for s in (suppliers_result.get("data") or [])
    ) or "<tr><td colspan='5'>Nenhuma oferta vinculada.</td></tr>"

    history_rows = "".join(
        f"<tr><td>{s18_escape(h.get('created_at'))}</td><td>{s18_escape(h.get('event_type'))}</td><td>{s18_escape(h.get('message'))}</td><td>{s18_escape(h.get('source'))}</td></tr>"
        for h in (history_result.get("data") or [])
    ) or "<tr><td colspan='4'>Sem histórico.</td></tr>"

    inventory = (inventory_result.get("data") or [{}])[0]
    content = f"""
<div class='grid'>
<div class='metric'><span>SKU</span><strong>{s18_escape(product.get('sku'))}</strong></div>
<div class='metric'><span>Status</span><strong>{s18_escape(product.get('internal_status') or 'draft')}</strong></div>
<div class='metric'><span>Estoque</span><strong>{s18_escape(inventory.get('available', 0))}</strong></div>
<div class='metric'><span>Venda</span><strong>{s18_money(product.get('sale_price'))}</strong></div>
</div>
<div class='card'>
<h2>{s18_escape(product.get('name'))}</h2>
<p><b>Marca:</b> {s18_escape(product.get('brand') or '-')}</p>
<p><b>Modelo:</b> {s18_escape(product.get('model') or '-')}</p>
<p><b>Categoria ML:</b> {s18_escape(product.get('ml_category_id') or '-')}</p>
<p><b>EAN:</b> {s18_escape(product.get('ean') or '-')}</p>
<p><b>SEO:</b> {s18_escape(product.get('seo_name') or '-')}</p>
<p><b>NCM:</b> {s18_escape(product.get('ncm') or '-')}</p>
<p><b>Dimensões:</b> {s18_escape(product.get('height_cm') or 0)} × {s18_escape(product.get('width_cm') or 0)} × {s18_escape(product.get('length_cm') or 0)} cm</p>
<p><b>Peso:</b> {s18_escape(product.get('weight_kg') or 0)} kg</p>
<p><b>Descrição:</b><br>{s18_escape(product.get('description') or '-')}</p>
<a class='btn' href='/product-master/{product_id}/edit'>Editar</a>
<a class='btn' href='/product-master/{product_id}/images'>Imagens</a>
<a class='btn' href='/product-master/{product_id}/attributes'>Atributos</a><a class='btn' href='/product-master/{product_id}/listing'>Criar anúncio ML</a>
</div>
<div class='card'><h2>Imagens</h2>{image_cards}</div>
<div class='card'>
<h2>Atributos</h2>
<table><thead><tr><th>Nome</th><th>Valor</th><th>Unidade</th><th>Origem</th></tr></thead><tbody>{attr_rows}</tbody></table>
</div>
<div class='card'>
<h2>Fornecedores / Ofertas</h2>
<table><thead><tr><th>SKU fornecedor</th><th>Custo</th><th>Estoque</th><th>Prioridade</th><th>Preferido</th></tr></thead><tbody>{supplier_rows}</tbody></table>
</div>
<div class='card'>
<h2>Histórico</h2>
<table><thead><tr><th>Data</th><th>Evento</th><th>Mensagem</th><th>Origem</th></tr></thead><tbody>{history_rows}</tbody></table>
</div>
"""
    return HTMLResponse(shell(f"Produto {product.get('sku')}", content))


@app.get("/product-master/{product_id}/edit", response_class=HTMLResponse)
async def product_master_edit_page(product_id: str):
    product = await s18_get_product(product_id)
    if not product:
        return HTMLResponse(shell("Produto", "<div class='card'><h2>Produto não encontrado.</h2></div>"), status_code=404)

    def val(key):
        return s18_escape(product.get(key) if product.get(key) is not None else "")

    content = f"""
<div class='card'>
<h2>Editar Produto Mestre</h2>
<form method='post' action='/api/product-master/{product_id}/update'>
<label>SKU</label><input name='sku' value='{val("sku")}' required>
<label>EAN/GTIN</label><input name='ean' value='{val("ean")}'>
<label>Nome</label><input name='name' value='{val("name")}' required>
<label>Nome SEO</label><input name='seo_name' value='{val("seo_name")}'>
<label>Marca</label><input name='brand' value='{val("brand")}'>
<label>Modelo</label><input name='model' value='{val("model")}' placeholder='Ex.: GM-01'>
<label>Categoria Mercado Livre</label><input name='ml_category_id' value='{val("ml_category_id")}' placeholder='Ex.: MLB1648'>
<label>Descrição curta</label><input name='short_description' value='{val("short_description")}'>
<label>Descrição longa</label><textarea name='description' style='width:100%;min-height:120px;padding:10px;border:1px solid #cbd5e1;border-radius:8px'>{val("description")}</textarea>
<label>Custo</label><input name='cost_price' value='{val("cost_price")}'>
<label>Venda</label><input name='sale_price' value='{val("sale_price")}'>
<label>Peso (kg)</label><input name='weight_kg' value='{val("weight_kg")}'>
<label>Altura</label><input name='height_cm' value='{val("height_cm")}'>
<label>Largura</label><input name='width_cm' value='{val("width_cm")}'>
<label>Comprimento</label><input name='length_cm' value='{val("length_cm")}'>
<label>NCM</label><input name='ncm' value='{val("ncm")}'>
<label>Garantia (meses)</label><input name='warranty_months' value='{val("warranty_months")}'>
<label>Imagem principal</label><input name='primary_image_url' value='{val("primary_image_url")}'>
<label>Status interno</label>
<select name='internal_status' style='width:100%;padding:10px;border:1px solid #cbd5e1;border-radius:8px;margin:5px 0 12px'>
<option value='draft' {'selected' if product.get('internal_status') == 'draft' else ''}>Draft</option>
<option value='ready' {'selected' if product.get('internal_status') == 'ready' else ''}>Ready</option>
<option value='paused' {'selected' if product.get('internal_status') == 'paused' else ''}>Paused</option>
<option value='archived' {'selected' if product.get('internal_status') == 'archived' else ''}>Archived</option>
</select>
<button type='submit'>Salvar alterações</button>
</form>
</div>
"""
    return HTMLResponse(shell("Editar Produto", content))


@app.post("/api/product-master/{product_id}/update")
async def product_master_update(product_id: str, request: Request):
    current = await s18_get_product(product_id)
    if not current:
        return JSONResponse(status_code=404, content={"success": False, "error": "Produto não encontrado."})

    form = await request.form()
    payload = {
        "sku": str(form.get("sku") or "").strip(),
        "ean": str(form.get("ean") or "").strip() or None,
        "name": str(form.get("name") or "").strip(),
        "seo_name": str(form.get("seo_name") or "").strip() or None,
        "brand": str(form.get("brand") or "").strip() or None,
        "model": str(form.get("model") or "").strip() or None,
        "ml_category_id": str(form.get("ml_category_id") or "").strip() or None,
        "short_description": str(form.get("short_description") or "").strip() or None,
        "description": str(form.get("description") or "").strip() or None,
        "cost_price": s18_decimal(form.get("cost_price"), 0),
        "sale_price": s18_decimal(form.get("sale_price"), 0),
        "weight_kg": s18_decimal(form.get("weight_kg"), 0),
        "height_cm": s18_decimal(form.get("height_cm"), 0),
        "width_cm": s18_decimal(form.get("width_cm"), 0),
        "length_cm": s18_decimal(form.get("length_cm"), 0),
        "ncm": str(form.get("ncm") or "").strip() or None,
        "warranty_months": s18_int(form.get("warranty_months"), 0),
        "primary_image_url": str(form.get("primary_image_url") or "").strip() or None,
        "internal_status": str(form.get("internal_status") or "draft"),
        "sync_status": "pending"
    }

    updated = await store.update("products", f"id=eq.{quote(product_id, safe='-')}", payload)
    if not updated.get("success"):
        return JSONResponse(status_code=400, content={"success": False, "error": updated.get("error") or updated.get("raw"), "result": updated})

    changed = {}
    for key, value in payload.items():
        if str(current.get(key)) != str(value):
            changed[key] = {"old": current.get(key), "new": value}
            await s18_history(product_id, "updated", f"Campo {key} alterado", key, current.get(key), value)

    await store.insert("logs", {
        "company_id": DEFAULT_COMPANY_ID,
        "event_type": "product_master_update",
        "level": "info",
        "message": f"Produto {payload.get('sku')} atualizado",
        "payload": {"product_id": product_id, "changed": changed}
    })
    return RedirectResponse(f"/product-master/{product_id}", status_code=303)


@app.get("/product-master/{product_id}/images", response_class=HTMLResponse)
async def product_master_images_page(product_id: str):
    product = await s18_get_product(product_id)
    if not product:
        return HTMLResponse(shell("Imagens", "<div class='card'><h2>Produto não encontrado.</h2></div>"), status_code=404)

    result = await store.select(
        "product_images",
        f"select=*&product_id=eq.{quote(product_id, safe='-')}&deleted_at=is.null&order=position.asc,created_at.asc"
    )
    images = result.get("data") or []

    cards = ""
    for image in images:
        image_id = image.get("id")
        url = image.get("url") or ""
        valid_url = str(url).lower().startswith(("https://", "http://"))
        badge = "Principal" if image.get("is_main") else f"Posição {image.get('position', 0)}"
        validation = image.get("validation_status") or ("pending" if valid_url else "invalid")
        cards += f"""
<div class='card' style='width:280px;display:inline-block;vertical-align:top;margin:0 12px 12px 0'>
<div style='height:190px;display:grid;place-items:center;background:#f8fafc;border-radius:10px;overflow:hidden'>
{"<img src='" + s18_escape(url) + "' style='max-width:100%;max-height:190px;object-fit:contain'>" if valid_url else "<div style='padding:20px;text-align:center;color:#b91c1c'>Imagem local/inválida</div>"}
</div>
<h3 style='margin-bottom:5px'>{s18_escape(image.get('file_name') or 'Imagem')}</h3>
<p><b>{s18_escape(badge)}</b> · Validação: {s18_escape(validation)}</p>
<p style='overflow-wrap:anywhere;font-size:12px'>{s18_escape(url)}</p>

<form method='post' action='/api/image-manager/{image_id}/main' style='display:inline'>
<button type='submit'>⭐ Tornar principal</button>
</form>

<form method='post' action='/api/image-manager/{image_id}/move' style='display:inline'>
<input type='hidden' name='direction' value='up'>
<button type='submit'>↑</button>
</form>

<form method='post' action='/api/image-manager/{image_id}/move' style='display:inline'>
<input type='hidden' name='direction' value='down'>
<button type='submit'>↓</button>
</form>

<button type='button' onclick="navigator.clipboard.writeText('{s18_escape(url)}');this.innerText='Copiado!'">📋 Copiar URL</button>
<a class='btn' href='{s18_escape(url) if valid_url else "#"}' target='_blank'>Abrir</a>

<form method='post' action='/api/image-manager/{image_id}/delete'
      onsubmit="return confirm('Excluir esta imagem do Product Master e do Supabase Storage?');"
      style='margin-top:10px'>
<button type='submit' style='background:#b91c1c'>🗑 Excluir</button>
</form>
</div>
"""

    if not cards:
        cards = "<div class='card'><p>Nenhuma imagem cadastrada.</p></div>"

    content = f"""
<div class='card'>
<h2>Gerenciador de Imagens — {s18_escape(product.get('sku'))}</h2>
<p>Envie JPG, PNG ou WEBP. O CommerceHub gera a URL pública automaticamente.</p>
<form method='post' action='/api/storage/products/{product_id}/upload' enctype='multipart/form-data'>
<label>Selecionar imagem</label>
<input type='file' name='file' accept='image/jpeg,image/png,image/webp' required>
<label>Texto alternativo</label>
<input name='alt_text' placeholder='Descrição da imagem'>
<label>Posição</label>
<input name='position' value='{len(images)}'>
<label><input type='checkbox' name='is_main' value='true' style='width:auto'> Imagem principal</label><br><br>
<button type='submit'>Enviar imagem</button>
</form>
<p><a class='btn' href='/api/storage/products/{product_id}/validate'>Validar todas as imagens</a></p>
</div>
<div style='white-space:normal'>{cards}</div>
"""
    return HTMLResponse(shell("Image Manager Enterprise", content))


@app.post("/api/product-master/{product_id}/images")
async def product_master_add_image(product_id: str, request: Request):
    product = await s18_get_product(product_id)
    if not product:
        return JSONResponse(status_code=404, content={"success": False, "error": "Produto não encontrado."})

    form = await request.form()
    url = str(form.get("url") or "").strip()
    if not url:
        return JSONResponse(status_code=400, content={"success": False, "error": "URL obrigatória."})
    if not url.lower().startswith(("https://", "http://")):
        return JSONResponse(status_code=400, content={
            "success": False,
            "error": "Use uma URL pública iniciada por https://. Caminhos locais como C:\\Users\\... não são aceitos."
        })

    is_main = str(form.get("is_main") or "").lower() == "true"
    payload = {
        "company_id": DEFAULT_COMPANY_ID,
        "product_id": product_id,
        "url": url,
        "position": s18_int(form.get("position"), 0),
        "is_main": is_main,
        "alt_text": str(form.get("alt_text") or "").strip() or None,
        "source": "commercehub",
        "hash": hashlib.sha256(url.encode("utf-8")).hexdigest()
    }
    created = await store.insert("product_images", payload)
    if is_main and created.get("success"):
        await store.update("products", f"id=eq.{quote(product_id, safe='-')}", {"primary_image_url": url, "sync_status": "pending"})
    await s18_history(product_id, "image_added", "Imagem adicionada ao produto", payload={"url": url, "is_main": is_main})
    return RedirectResponse(f"/product-master/{product_id}/images", status_code=303)


@app.get("/product-master/{product_id}/attributes", response_class=HTMLResponse)
async def product_master_attributes_page(product_id: str):
    product = await s18_get_product(product_id)
    if not product:
        return HTMLResponse(shell("Atributos", "<div class='card'><h2>Produto não encontrado.</h2></div>"), status_code=404)

    result = await store.select("product_attributes", f"select=*&product_id=eq.{quote(product_id, safe='-')}&order=name.asc")
    rows = "".join(
        f"<tr><td>{s18_escape(a.get('name'))}</td><td>{s18_escape(a.get('value'))}</td><td>{s18_escape(a.get('unit') or '')}</td><td>{'Sim' if a.get('is_required') else 'Não'}</td></tr>"
        for a in (result.get("data") or [])
    ) or "<tr><td colspan='4'>Nenhum atributo.</td></tr>"

    content = f"""
<div class='card'>
<h2>Adicionar atributo — {s18_escape(product.get('sku'))}</h2>
<form method='post' action='/api/product-master/{product_id}/attributes'>
<label>Nome</label><input name='name' required placeholder='Ex.: Cor'>
<label>Valor</label><input name='value' placeholder='Ex.: Preto'>
<label>Unidade</label><input name='unit' placeholder='Ex.: cm'>
<label><input type='checkbox' name='is_required' value='true' style='width:auto'> Obrigatório no marketplace</label><br><br>
<button type='submit'>Salvar atributo</button>
</form>
</div>
<div class='card'><table><thead><tr><th>Nome</th><th>Valor</th><th>Unidade</th><th>Obrigatório</th></tr></thead><tbody>{rows}</tbody></table></div>
"""
    return HTMLResponse(shell("Atributos do Produto", content))


@app.post("/api/product-master/{product_id}/attributes")
async def product_master_add_attribute(product_id: str, request: Request):
    product = await s18_get_product(product_id)
    if not product:
        return JSONResponse(status_code=404, content={"success": False, "error": "Produto não encontrado."})

    form = await request.form()
    name = str(form.get("name") or "").strip()
    if not name:
        return JSONResponse(status_code=400, content={"success": False, "error": "Nome obrigatório."})

    payload = {
        "company_id": DEFAULT_COMPANY_ID,
        "product_id": product_id,
        "name": name,
        "value": str(form.get("value") or "").strip() or None,
        "unit": str(form.get("unit") or "").strip() or None,
        "is_required": str(form.get("is_required") or "").lower() == "true",
        "source": "commercehub"
    }
    saved = await store.upsert("product_attributes", payload, "product_id,name")
    if not saved.get("success"):
        return JSONResponse(status_code=400, content={"success": False, "error": saved.get("error") or saved.get("raw")})
    await store.update("products", f"id=eq.{quote(product_id, safe='-')}", {"sync_status": "pending"})
    await s18_history(product_id, "attribute_saved", f"Atributo {name} salvo", payload=payload)
    return RedirectResponse(f"/product-master/{product_id}/attributes", status_code=303)


@app.get("/api/product-master/status")
async def product_master_status():
    tables = ["products", "product_images", "product_attributes", "product_suppliers", "product_history", "supplier_products", "inventory"]
    checks = {}
    for table in tables:
        result = await store.select(table, "select=*&limit=1")
        checks[table] = {
            "success": bool(result.get("success")),
            "status_code": result.get("status_code"),
            "rows": len(result.get("data") or []),
            "error": str(result.get("error") or result.get("raw") or "")[:500]
        }

    product_count = await store.select("products", "select=id&company_id=eq." + quote(DEFAULT_COMPANY_ID, safe="-"))
    supplier_link_count = await store.select("product_suppliers", "select=id&company_id=eq." + quote(DEFAULT_COMPANY_ID, safe="-"))
    return {
        "success": all(item["success"] for item in checks.values()),
        "version": APP_VERSION,
        "module": "product_master",
        "checks": checks,
        "counts": {
            "products": len(product_count.get("data") or []),
            "supplier_links": len(supplier_link_count.get("data") or [])
        },
        "pages": ["/product-master", "/product-master/new", "/product-master/sql"]
    }


@app.get("/api/product-master/search")
async def product_master_search(q: str = ""):
    result = await store.select("products", "select=*&company_id=eq." + quote(DEFAULT_COMPANY_ID, safe="-") + "&order=updated_at.desc&limit=200")
    products = result.get("data") or []
    q_lower = str(q or "").lower().strip()
    if q_lower:
        products = [
            p for p in products
            if q_lower in str(p.get("sku") or "").lower()
            or q_lower in str(p.get("ean") or "").lower()
            or q_lower in str(p.get("name") or "").lower()
            or q_lower in str(p.get("brand") or "").lower()
        ]
    return {"success": True, "version": APP_VERSION, "query": q, "count": len(products), "data": products}


# ==========================================================
# SPRINT 19 - LISTING ENGINE MERCADO LIVRE
# Draft, categorização, validação, publicação e sincronização.
# ==========================================================

def s19e(value):
    value = str(value if value is not None else "")
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def s19money(value):
    try:
        return f"R$ {float(value or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def s19int(value, default=0):
    try:
        return int(float(str(value or default).replace(",", ".")))
    except Exception:
        return default


def s19float(value, default=0.0):
    try:
        text = str(value or "").strip().replace("R$", "").replace(" ", "")
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", ".")
        return float(text) if text else default
    except Exception:
        return default


async def s19_get_listing_by_product(product_id):
    result = await store.select(
        "listings",
        f"select=*&company_id=eq.{DEFAULT_COMPANY_ID}&product_id=eq.{quote(str(product_id), safe='-')}&marketplace=eq.mercado_livre&limit=1"
    )
    rows = result.get("data") or []
    return rows[0] if rows else None


async def s19_get_listing(listing_id):
    result = await store.select(
        "listings",
        f"select=*&id=eq.{quote(str(listing_id), safe='-')}&limit=1"
    )
    rows = result.get("data") or []
    return rows[0] if rows else None


async def s19_history(listing_id, product_id, event_type, message, old_status=None, new_status=None, payload=None):
    return await store.insert("listing_history", {
        "company_id": DEFAULT_COMPANY_ID,
        "listing_id": listing_id,
        "product_id": product_id,
        "event_type": event_type,
        "old_status": old_status,
        "new_status": new_status,
        "message": message,
        "payload": payload or {}
    })


async def s19_product_context(product_id):
    product = await s18_get_product(product_id)
    if not product:
        return None

    inventory_result = await store.select(
        "inventory",
        f"select=*&product_id=eq.{quote(str(product_id), safe='-')}&limit=1"
    )
    images_result = await store.select(
        "product_images",
        f"select=*&product_id=eq.{quote(str(product_id), safe='-')}&order=position.asc"
    )
    attrs_result = await store.select(
        "product_attributes",
        f"select=*&product_id=eq.{quote(str(product_id), safe='-')}&order=name.asc"
    )
    marketplace_attrs_result = await store.select(
        "product_marketplace_attributes",
        f"select=*&product_id=eq.{quote(str(product_id), safe='-')}&marketplace=eq.mercado_livre"
    )

    inventory = (inventory_result.get("data") or [{}])[0]
    images = images_result.get("data") or []
    attributes = attrs_result.get("data") or []
    marketplace_attributes = marketplace_attrs_result.get("data") or []

    picture_urls = []
    if product.get("primary_image_url"):
        picture_urls.append(product.get("primary_image_url"))
    for image in images:
        url = image.get("url")
        if url and url not in picture_urls:
            picture_urls.append(url)

    return {
        "product": product,
        "inventory": inventory,
        "images": picture_urls,
        "attributes": attributes,
        "marketplace_attributes": marketplace_attributes
    }


def s19_local_validation(context, listing):
    product = context["product"]
    inventory = context["inventory"]
    images = context["images"]
    errors = []
    warnings = []

    title = str(listing.get("title") or product.get("name") or "").strip()
    category_id = str(listing.get("category_id") or "").strip()
    price = s19float(listing.get("price") or product.get("sale_price"), 0)
    quantity = s19int(listing.get("available_quantity") or inventory.get("available"), 0)

    if not title:
        errors.append("Título obrigatório.")
    if len(title) > 60:
        warnings.append("O título possui mais de 60 caracteres e pode ser rejeitado ou truncado.")
    if not category_id:
        errors.append("Categoria do Mercado Livre obrigatória.")
    if price <= 0:
        errors.append("Preço deve ser maior que zero.")
    if quantity < 0:
        errors.append("Estoque não pode ser negativo.")
    if not images:
        errors.append("Adicione ao menos uma imagem pública ao Product Master.")
    if str(product.get("internal_status") or "draft") != "ready":
        warnings.append("O produto ainda não está com status interno 'ready'.")
    if not product.get("ean"):
        has_empty_gtin_reason = any(
            str(row.get("attribute_id") or "").upper() == "EMPTY_GTIN_REASON"
            and bool(row.get("value_id") or row.get("value_name"))
            for row in context.get("marketplace_attributes") or []
        )
        if not has_empty_gtin_reason:
            warnings.append("Produto sem EAN/GTIN e sem motivo de ausência informado.")
    if not product.get("brand"):
        warnings.append("Produto sem marca.")
    if not product.get("description"):
        warnings.append("Produto sem descrição longa.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "title": title,
            "category_id": category_id,
            "price": price,
            "available_quantity": quantity,
            "pictures": len(images),
            "gtin_resolution": (
                "gtin" if product.get("ean") else
                "empty_gtin_reason" if any(
                    str(row.get("attribute_id") or "").upper() == "EMPTY_GTIN_REASON"
                    and bool(row.get("value_id") or row.get("value_name"))
                    for row in context.get("marketplace_attributes") or []
                ) else "missing"
            )
        }
    }


def s19_build_ml_payload(context, listing, mode="user_product"):
    product = context["product"]
    inventory = context["inventory"]
    pictures = [{"source": url} for url in context["images"]]
    attributes = []

    if product.get("ean"):
        attributes.append({"id": "GTIN", "value_name": str(product.get("ean"))})
    if product.get("brand"):
        attributes.append({"id": "BRAND", "value_name": str(product.get("brand"))})

    for attr in context["attributes"]:
        attr_name = str(attr.get("name") or "").strip()
        attr_value = str(attr.get("value") or "").strip()
        if attr_name and attr_value and attr_name.upper() not in ["GTIN", "BRAND"]:
            attributes.append({
                "id": attr_name.upper().replace(" ", "_"),
                "value_name": attr_value
            })

    title = str(listing.get("title") or product.get("name") or "").strip()[:60]
    family_name = str(
        product.get("seo_name")
        or product.get("name")
        or listing.get("title")
        or ""
    ).strip()[:60]

    payload = {
        "category_id": listing.get("category_id"),
        "price": s19float(listing.get("price") or product.get("sale_price"), 0),
        "currency_id": listing.get("currency_id") or "BRL",
        "available_quantity": s19int(listing.get("available_quantity") or inventory.get("available"), 0),
        "buying_mode": listing.get("buying_mode") or "buy_it_now",
        "condition": listing.get("condition") or "new",
        "listing_type_id": listing.get("listing_type_id") or "gold_special",
        "pictures": pictures,
        "attributes": attributes
    }

    # Novo padrão User Products: family_name sem title.
    if mode == "user_product":
        payload["family_name"] = family_name
    else:
        payload["title"] = title

    return payload


def s202_ml_error_text(result):
    data = result.get("data") if isinstance(result, dict) else {}
    return " ".join([
        str(result.get("error") or "") if isinstance(result, dict) else "",
        str(result.get("raw") or "") if isinstance(result, dict) else "",
        str(data.get("message") or "") if isinstance(data, dict) else "",
        str(data.get("error") or "") if isinstance(data, dict) else "",
    ]).lower()


async def s202_publish_with_fallback(context, listing):
    preflight = await s24_metadata_preflight(context, listing)
    if not preflight.get("success"):
        return {
            "success": False,
            "mode": "marketplace_metadata_preflight",
            "payload": preflight.get("payload_preview") or {},
            "result": {
                "success": False,
                "status_code": 422,
                "data": {
                    "message": "marketplace_metadata_preflight_failed",
                    "error": "O anúncio foi bloqueado pelas regras oficiais ou aprendidas do marketplace.",
                    "preflight": preflight,
                },
                "error": "Marketplace Metadata Preflight falhou.",
                "transport": "commercehub-local",
            },
            "attempts": 0,
        }

    category_rule = await s23_product_category_rule(
        context["product"].get("id"),
        listing.get("category_id")
    )
    feedback_rule = await s23_product_feedback_rule(context["product"].get("id"), listing.get("category_id"))

    if feedback_rule and category_rule.get("mode") == "empty_gtin_reason":
        category_rule["allowed_to_publish"] = False
        category_rule["mode"] = "blocked_by_ml_feedback"
        category_rule["blocking_reason"] = (
            "O Mercado Livre já confirmou que esta categoria exige GTIN válido."
        )

    if not category_rule.get("allowed_to_publish"):
        return {
            "success": False,
            "mode": "category_rule_validation",
            "payload": {},
            "result": {
                "success": False,
                "status_code": 422,
                "data": {
                    "message": "category_rule_validation_failed",
                    "error": category_rule.get("blocking_reason"),
                    "category_rule": category_rule,
                },
                "error": "Validação inteligente de categoria falhou.",
                "transport": "commercehub-local",
            },
            "attempts": 0,
        }

    attribute_validation = await s212_attribute_validation(
        context["product"].get("id"),
        listing.get("category_id")
    )
    if not attribute_validation.get("valid"):
        return {
            "success": False,
            "mode": "local_attribute_validation",
            "payload": {},
            "result": {
                "success": False,
                "status_code": 422,
                "data": {
                    "message": "attribute_validation_failed",
                    "error": "Corrija os atributos obrigatórios ou inválidos antes de publicar.",
                    "validation": attribute_validation,
                },
                "error": "Validação local de atributos falhou.",
                "transport": "commercehub-local",
            },
            "attempts": 0,
        }

    # Primeira tentativa: User Products.
    first_payload = s19_build_ml_payload(context, listing, mode="user_product")
    first_payload["attributes"] = await s21_payload_attributes(context["product"].get("id"), listing.get("category_id"), first_payload.get("attributes"))
    first_result = await ml_request("/items", method="POST", payload=first_payload)
    if first_result.get("success"):
        return {
            "success": True,
            "mode": "user_product",
            "payload": first_payload,
            "result": first_result,
            "attempts": 1,
        }

    error_text = s202_ml_error_text(first_result)

    # Se a API rejeitar family_name ou exigir title, tenta o fluxo clássico.
    should_try_classic = (
        "family_name" in error_text
        or "fields [family_name] are invalid" in error_text
        or "title" in error_text and "required" in error_text
    )

    if should_try_classic:
        second_payload = s19_build_ml_payload(context, listing, mode="classic")
        second_payload["attributes"] = await s21_payload_attributes(context["product"].get("id"), listing.get("category_id"), second_payload.get("attributes"))
        second_result = await ml_request("/items", method="POST", payload=second_payload)
        return {
            "success": bool(second_result.get("success")),
            "mode": "classic",
            "payload": second_payload,
            "result": second_result,
            "first_attempt": {
                "payload": first_payload,
                "result": first_result,
            },
            "attempts": 2,
        }

    return {
        "success": False,
        "mode": "user_product",
        "payload": first_payload,
        "result": first_result,
        "attempts": 1,
    }


@app.get("/listing-engine", response_class=HTMLResponse)
async def listing_engine_page(request: Request):
    status_filter = str(request.query_params.get("status") or "").strip()
    query = "select=*&company_id=eq." + quote(DEFAULT_COMPANY_ID, safe="-") + "&marketplace=eq.mercado_livre"
    if status_filter:
        query += "&status=eq." + quote(status_filter, safe="_-")
    query += "&order=updated_at.desc&limit=100"

    listings_result = await store.select("listings", query)
    listings = listings_result.get("data") or []

    rows = ""
    for listing in listings:
        product = await s18_get_product(listing.get("product_id"))
        rows += f"""
<tr>
<td>{s19e((product or {}).get('sku') or '-')}</td>
<td>{s19e(listing.get('title'))}</td>
<td>{s19e(listing.get('category_id') or '-')}</td>
<td>{s19money(listing.get('price'))}</td>
<td>{s19e(listing.get('available_quantity'))}</td>
<td>{s19e(listing.get('status'))}</td>
<td>{s19e(listing.get('validation_status') or 'pending')}</td>
<td>{s19e(listing.get('external_id') or '-')}</td>
<td><a class='btn' href='/listing-engine/{listing.get("id")}'>Abrir</a></td>
</tr>
"""

    if not rows:
        rows = "<tr><td colspan='9'>Nenhum rascunho de anúncio criado.</td></tr>"

    content = f"""
<div class='grid'>
<div class='metric'><span>Anúncios</span><strong>{len(listings)}</strong></div>
<div class='metric'><span>Marketplace</span><strong>Mercado Livre</strong></div>
<div class='metric'><span>Publicação</span><strong>Com confirmação</strong></div>
<div class='metric'><span>Origem</span><strong>Product Master</strong></div>
</div>
<div class='card'>
<h2>Listing Engine</h2>
<p>Crie um rascunho a partir do Product Master, valide os dados e publique somente após confirmação explícita.</p>
<a class='btn' href='/product-master'>Selecionar produto</a>
<a class='btn' href='/listing-engine/sql'>SQL Sprint 19</a>
<a class='btn' href='/api/listing-engine/status'>Status do módulo</a>
<a class='btn' href='/api/ml/listing-types'>Tipos de anúncio</a>
</div>
<div class='card'>
<table>
<thead><tr><th>SKU</th><th>Título</th><th>Categoria</th><th>Preço</th><th>Qtd</th><th>Status</th><th>Validação</th><th>ID ML</th><th>Ação</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>
"""
    return HTMLResponse(shell("Listing Engine", content))


@app.get("/listing-engine/sql", response_class=HTMLResponse)
async def listing_engine_sql_page():
    sql_text = open("sprint19_listing_engine.sql", "r", encoding="utf-8").read()
    return HTMLResponse(shell(
        "SQL Sprint 19",
        f"<div class='card'><h2>Migration Listing Engine</h2><p>Copie e execute no Supabase SQL Editor.</p><pre>{s19e(sql_text)}</pre></div>"
    ))


@app.get("/product-master/{product_id}/listing", response_class=HTMLResponse)
async def listing_from_product_page(product_id: str):
    context = await s19_product_context(product_id)
    if not context:
        return HTMLResponse(shell("Anúncio", "<div class='card'><h2>Produto não encontrado.</h2></div>"), status_code=404)

    product = context["product"]
    inventory = context["inventory"]
    current = await s19_get_listing_by_product(product_id) or {}
    title = current.get("title") or product.get("seo_name") or product.get("name") or ""
    description = current.get("description") or product.get("description") or product.get("short_description") or ""
    price = current.get("price") if current.get("price") is not None else product.get("sale_price")
    quantity = current.get("available_quantity") if current.get("available_quantity") is not None else inventory.get("available", 0)

    content = f"""
<div class='card'>
<h2>Preparar anúncio — {s19e(product.get('sku'))}</h2>
<p><b>Produto:</b> {s19e(product.get('name'))}</p>
<p><b>Imagens disponíveis:</b> {len(context['images'])}</p>
<form method='post' action='/api/listing-engine/draft'>
<input type='hidden' name='product_id' value='{s19e(product_id)}'>
<label>Título do anúncio</label>
<input name='title' maxlength='60' value='{s19e(title)}' required>
<label>Descrição</label>
<textarea name='description' style='width:100%;min-height:160px;padding:10px;border:1px solid #cbd5e1;border-radius:8px'>{s19e(description)}</textarea>
<label>Categoria Mercado Livre</label>
<input name='category_id' value='{s19e(current.get("category_id") or "")}' placeholder='Ex.: MLB1648' required>
<p><a class='btn' href='/api/ml/category-predict?q={quote(str(product.get("name") or ""))}'>Sugerir categoria</a></p>
<label>Preço</label><input name='price' value='{s19e(price)}' required>
<label>Quantidade disponível</label><input name='available_quantity' value='{s19e(quantity)}' required>
<label>Tipo de anúncio</label>
<select name='listing_type_id' style='width:100%;padding:10px;border:1px solid #cbd5e1;border-radius:8px;margin:5px 0 12px'>
<option value='gold_special' {'selected' if current.get('listing_type_id','gold_special') == 'gold_special' else ''}>Clássico / gold_special</option>
<option value='gold_pro' {'selected' if current.get('listing_type_id') == 'gold_pro' else ''}>Premium / gold_pro</option>
<option value='free' {'selected' if current.get('listing_type_id') == 'free' else ''}>Grátis / free</option>
</select>
<label>Condição</label>
<select name='condition' style='width:100%;padding:10px;border:1px solid #cbd5e1;border-radius:8px;margin:5px 0 12px'>
<option value='new' {'selected' if current.get('condition','new') == 'new' else ''}>Novo</option>
<option value='used' {'selected' if current.get('condition') == 'used' else ''}>Usado</option>
</select>
<label>Garantia</label><input name='warranty' value='{s19e(current.get("warranty") or "")}' placeholder='Ex.: Garantia do vendedor: 3 meses'>
<button type='submit'>Salvar rascunho</button>
</form>
</div>
"""
    return HTMLResponse(shell("Preparar anúncio", content))


@app.post("/api/listing-engine/draft")
async def listing_save_draft(request: Request):
    form = await request.form()
    product_id = str(form.get("product_id") or "").strip()
    context = await s19_product_context(product_id)
    if not context:
        return JSONResponse(status_code=404, content={"success": False, "error": "Produto não encontrado."})

    current = await s19_get_listing_by_product(product_id)
    listing_id = current.get("id") if current else str(uuid.uuid4())
    old_status = current.get("status") if current else None

    payload = {
        "id": listing_id,
        "company_id": DEFAULT_COMPANY_ID,
        "product_id": product_id,
        "marketplace": "mercado_livre",
        "external_id": current.get("external_id") if current else None,
        "title": str(form.get("title") or "").strip(),
        "description": str(form.get("description") or "").strip() or None,
        "category_id": str(form.get("category_id") or "").strip(),
        "price": s19float(form.get("price"), 0),
        "available_quantity": s19int(form.get("available_quantity"), 0),
        "listing_type_id": str(form.get("listing_type_id") or "gold_special"),
        "condition": str(form.get("condition") or "new"),
        "currency_id": "BRL",
        "buying_mode": "buy_it_now",
        "warranty": str(form.get("warranty") or "").strip() or None,
        "status": current.get("status") if current and current.get("external_id") else "draft",
        "validation_status": "pending",
        "payload": current.get("payload") if current else {}
    }

    saved = await store.upsert("listings", payload, "company_id,product_id,marketplace")
    if saved.get("success") and payload.get("category_id"):
        await store.update(
            "products",
            f"id=eq.{quote(product_id, safe='-')}",
            {"ml_category_id": payload.get("category_id"), "sync_status": "pending"}
        )
    if not saved.get("success"):
        return JSONResponse(status_code=400, content={"success": False, "error": saved.get("error") or saved.get("raw")})

    await s19_history(
        listing_id, product_id, "draft_saved", "Rascunho do anúncio salvo.",
        old_status, payload["status"], {"category_id": payload["category_id"]}
    )
    return RedirectResponse(f"/listing-engine/{listing_id}", status_code=303)


@app.get("/listing-engine/{listing_id}", response_class=HTMLResponse)
async def listing_details_page(listing_id: str):
    listing = await s19_get_listing(listing_id)
    if not listing:
        return HTMLResponse(shell("Anúncio", "<div class='card'><h2>Anúncio não encontrado.</h2></div>"), status_code=404)

    context = await s19_product_context(listing.get("product_id"))
    if not context:
        return HTMLResponse(shell("Anúncio", "<div class='card'><h2>Produto relacionado não encontrado.</h2></div>"), status_code=404)

    product = context["product"]
    validation = s19_local_validation(context, listing)
    history_result = await store.select(
        "listing_history",
        f"select=*&listing_id=eq.{quote(listing_id, safe='-')}&order=created_at.desc&limit=50"
    )

    errors_html = "".join(f"<li style='color:#b91c1c'>{s19e(x)}</li>" for x in validation["errors"]) or "<li>Nenhum erro local.</li>"
    warnings_html = "".join(f"<li style='color:#92400e'>{s19e(x)}</li>" for x in validation["warnings"]) or "<li>Nenhum alerta.</li>"
    history_rows = "".join(
        f"<tr><td>{s19e(h.get('created_at'))}</td><td>{s19e(h.get('event_type'))}</td><td>{s19e(h.get('old_status') or '-')}</td><td>{s19e(h.get('new_status') or '-')}</td><td>{s19e(h.get('message'))}</td></tr>"
        for h in (history_result.get("data") or [])
    ) or "<tr><td colspan='5'>Sem histórico.</td></tr>"

    publish_box = ""
    if listing.get("external_id"):
        publish_box = f"""
<div class='card'>
<h2>Anúncio publicado</h2>
<p><b>ID:</b> {s19e(listing.get('external_id'))}</p>
<p><b>Status:</b> {s19e(listing.get('status'))}</p>
<p><b>Link:</b> <a href='{s19e(listing.get('permalink') or listing.get('item_url') or '#')}' target='_blank'>{s19e(listing.get('permalink') or listing.get('item_url') or '-')}</a></p>
<form method='post' action='/api/listing-engine/{listing_id}/sync'>
<button type='submit'>Sincronizar preço e estoque</button>
</form>
</div>
"""
    else:
        publish_box = f"""
<div class='card'>
<h2>Publicação controlada</h2>
<p>Esta ação cria um anúncio real na conta conectada do Mercado Livre.</p>
<p><b>Modo manual:</b> digite <code>PUBLICAR</code> para publicar agora.</p>
<form method='post' action='/api/publication-readiness/listing/{listing_id}/publish'>
<label>Confirmação</label><input name='confirmation' placeholder='PUBLICAR' required>
<button type='submit'>Publicar agora no Mercado Livre</button>
</form>
<hr style='margin:22px 0'>
<h3>Modo automático</h3>
<p>Quando ativado, este rascunho poderá ser publicado pelo executor automático somente após passar em todas as validações.</p>
<form method='post' action='/api/listing-engine/{listing_id}/automatic'>
<input type='hidden' name='enabled' value='true'>
<button type='submit'>Ativar publicação automática para este anúncio</button>
</form>
</div>
"""

    content = f"""
<div class='grid'>
<div class='metric'><span>SKU</span><strong>{s19e(product.get('sku'))}</strong></div>
<div class='metric'><span>Status</span><strong>{s19e(listing.get('status'))}</strong></div>
<div class='metric'><span>Validação</span><strong>{'OK' if validation['valid'] else 'PENDENTE'}</strong></div>
<div class='metric'><span>Preço</span><strong>{s19money(listing.get('price'))}</strong></div>
</div>
<div class='card'>
<h2>{s19e(listing.get('title'))}</h2>
<p><b>Categoria:</b> {s19e(listing.get('category_id') or '-')}</p>
<p><b>Tipo:</b> {s19e(listing.get('listing_type_id'))}</p>
<p><b>Quantidade:</b> {s19e(listing.get('available_quantity'))}</p>
<p><b>Imagens:</b> {len(context['images'])}</p>
<p><b>Descrição:</b><br>{s19e(listing.get('description') or '-')}</p>
<a class='btn' href='/product-master/{product.get("id")}/listing'>Editar rascunho</a>
<a class='btn' href='/api/ml/categories/{quote(str(listing.get("category_id") or ""))}/attributes'>Atributos da categoria</a><a class='btn' href='/api/listing-engine/{listing_id}/readiness'>Verificar prontidão</a><a class='btn' href='/smart-category-engine/product/{product.get("id")}/category/{listing.get("category_id")}'>Atributos inteligentes</a><a class='btn' href='/category-rules/product/{product.get("id")}/category/{listing.get("category_id")}'>Regras da categoria</a><a class='btn' href='/metadata-preflight/listing/{listing_id}'>Metadata Preflight</a><a class='btn' href='/marketplace-intelligence/listing/{listing_id}'>Marketplace Intelligence</a><a class='btn' href='/publishing-lab/listing/{listing_id}'>Publishing Lab</a><a class='btn' href='/marketplace-rules/listing/{listing_id}'>Rules Engine</a><a class='btn' href='/marketplace-inspector/listing/{listing_id}'>Marketplace Inspector</a><a class='btn' href='/marketplace-knowledge/listing/{listing_id}'>Knowledge Engine</a><a class='btn' href='/publication-readiness/listing/{listing_id}'>Prontidão para Publicação</a><a class='btn' href='/gtin-discovery/listing/{listing_id}'>Descobrir GTIN</a><a class='btn' href='/gtin-intelligence/listing/{listing_id}'>GTIN Intelligence</a><a class='btn' href='/marketplace-auto-completer/listing/{listing_id}'>Auto Completar</a>
</div>
<div class='card'><h2>Erros</h2><ul>{errors_html}</ul><h2>Alertas</h2><ul>{warnings_html}</ul></div>
{publish_box}
<div class='card'>
<h2>Histórico</h2>
<table><thead><tr><th>Data</th><th>Evento</th><th>Anterior</th><th>Novo</th><th>Mensagem</th></tr></thead><tbody>{history_rows}</tbody></table>
</div>
"""
    return HTMLResponse(shell("Detalhes do anúncio", content))


@app.post("/api/listing-engine/{listing_id}/publish")
async def listing_publish(listing_id: str, request: Request):
    form = await request.form()
    confirmation = str(form.get("confirmation") or "").strip().upper()
    if confirmation != "PUBLICAR":
        return JSONResponse(status_code=400, content={
            "success": False,
            "error": "Confirmação inválida. Digite PUBLICAR."
        })

    listing = await s19_get_listing(listing_id)
    if not listing:
        return JSONResponse(status_code=404, content={"success": False, "error": "Anúncio não encontrado."})
    if listing.get("external_id"):
        return JSONResponse(status_code=409, content={"success": False, "error": "Este anúncio já possui ID do Mercado Livre."})

    context = await s19_product_context(listing.get("product_id"))
    validation = s19_local_validation(context, listing)
    if not validation["valid"]:
        await store.update(
            "listings",
            f"id=eq.{quote(listing_id, safe='-')}",
            {"validation_status": "failed", "last_error": json.dumps(validation, ensure_ascii=False)}
        )
        return JSONResponse(status_code=409, content={
            "success": False,
            "error": "O anúncio não passou na validação local.",
            "validation": validation
        })

    publish_attempt = await s202_publish_with_fallback(context, listing)
    payload = publish_attempt.get("payload") or {}
    result = publish_attempt.get("result") or {}
    if not publish_attempt.get("success"):
        try:
            await s25_record_error(
                context,
                listing,
                result,
                payload,
            )
        except Exception:
            pass

        try:
            await s23_record_ml_rule_feedback(
                context["product"].get("id"),
                listing.get("category_id"),
                result,
            )
        except Exception:
            pass
        error_text = str(result.get("error") or result.get("raw") or result.get("data") or "")[:3000]
        await store.update(
            "listings",
            f"id=eq.{quote(listing_id, safe='-')}",
            {"validation_status": "failed", "last_error": error_text, "payload": payload}
        )
        await s19_history(listing_id, listing.get("product_id"), "publish_failed", "Mercado Livre rejeitou a publicação.", listing.get("status"), listing.get("status"), {"result": result})
        return JSONResponse(status_code=400, content={
            "success": False,
            "error": "Falha ao publicar no Mercado Livre.",
            "result": result,
            "payload_sent": payload,
            "publish_mode": publish_attempt.get("mode"),
            "attempts": publish_attempt.get("attempts"),
            "first_attempt": publish_attempt.get("first_attempt")
        })

    item = result.get("data") or {}
    external_id = item.get("id")
    permalink = item.get("permalink")
    new_status = item.get("status") or "active"

    update_payload = {
        "external_id": external_id,
        "permalink": permalink,
        "item_url": permalink,
        "status": new_status,
        "validation_status": "published",
        "last_error": None,
        "payload": payload,
        "published_at": __import__("datetime").datetime.utcnow().isoformat(),
        "last_synced_at": __import__("datetime").datetime.utcnow().isoformat()
    }
    await store.update("listings", f"id=eq.{quote(listing_id, safe='-')}", update_payload)

    description = str(listing.get("description") or "").strip()
    description_result = None
    if external_id and description:
        description_result = await ml_request(
            f"/items/{external_id}/description",
            method="POST",
            payload={"plain_text": description}
        )

    await store.update(
        "products",
        f"id=eq.{quote(str(listing.get('product_id')), safe='-')}",
        {"sync_status": "synced", "last_synced_at": __import__("datetime").datetime.utcnow().isoformat()}
    )
    await s19_history(listing_id, listing.get("product_id"), "published", f"Anúncio {external_id} publicado no Mercado Livre.", listing.get("status"), new_status, {"item": item, "description": description_result})
    await store.insert("logs", {
        "company_id": DEFAULT_COMPANY_ID,
        "event_type": "mercado_livre_listing_published",
        "level": "info",
        "message": f"Produto publicado no Mercado Livre: {external_id}",
        "payload": {"listing_id": listing_id, "product_id": listing.get("product_id"), "external_id": external_id}
    })
    return RedirectResponse(f"/listing-engine/{listing_id}", status_code=303)


@app.post("/api/listing-engine/{listing_id}/sync")
async def listing_sync(listing_id: str):
    listing = await s19_get_listing(listing_id)
    if not listing or not listing.get("external_id"):
        return JSONResponse(status_code=404, content={"success": False, "error": "Anúncio publicado não encontrado."})

    context = await s19_product_context(listing.get("product_id"))
    price = s19float(context["product"].get("sale_price"), listing.get("price"))
    quantity = s19int(context["inventory"].get("available"), listing.get("available_quantity"))

    result = await ml_request(
        f"/items/{listing.get('external_id')}",
        method="PUT",
        payload={"price": price, "available_quantity": quantity}
    )
    if not result.get("success"):
        await store.update("listings", f"id=eq.{quote(listing_id, safe='-')}", {"last_error": str(result.get("error") or result.get("raw") or result.get("data"))[:3000]})
        return JSONResponse(status_code=400, content={"success": False, "result": result})

    item = result.get("data") or {}
    update_payload = {
        "price": price,
        "available_quantity": quantity,
        "status": item.get("status") or listing.get("status"),
        "permalink": item.get("permalink") or listing.get("permalink"),
        "last_synced_at": __import__("datetime").datetime.utcnow().isoformat(),
        "last_error": None
    }
    await store.update("listings", f"id=eq.{quote(listing_id, safe='-')}", update_payload)
    await s19_history(listing_id, listing.get("product_id"), "synced", "Preço e estoque sincronizados com o Mercado Livre.", listing.get("status"), update_payload["status"], {"price": price, "quantity": quantity})
    return RedirectResponse(f"/listing-engine/{listing_id}", status_code=303)


@app.get("/api/ml/category-predict")
async def ml_category_predict(q: str = ""):
    if not str(q or "").strip():
        return JSONResponse(status_code=400, content={"success": False, "error": "Informe q."})
    return await ml_request(
        "/sites/MLB/domain_discovery/search",
        params={"q": str(q).strip(), "limit": 8}
    )


@app.get("/api/ml/categories/{category_id}/attributes")
async def ml_category_attributes(category_id: str):
    return await ml_request(f"/categories/{quote(category_id, safe='-_')}/attributes")


@app.get("/api/ml/listing-types")
async def ml_listing_types():
    return await ml_request("/sites/MLB/listing_types")


@app.get("/api/listing-engine/status")
async def listing_engine_status():
    checks = {}
    for table in ["products", "inventory", "product_images", "product_attributes", "listings", "listing_history", "oauth_tokens"]:
        result = await store.select(table, "select=*&limit=1")
        checks[table] = {
            "success": bool(result.get("success")),
            "status_code": result.get("status_code"),
            "rows": len(result.get("data") or []),
            "error": str(result.get("error") or result.get("raw") or "")[:500]
        }

    me = await ml_request("/users/me")
    return {
        "success": all(item["success"] for item in checks.values()) and bool(me.get("success")),
        "version": APP_VERSION,
        "module": "listing_engine_mercado_livre",
        "mercado_livre_connected": bool(me.get("success")),
        "seller_id": (me.get("data") or {}).get("id"),
        "checks": checks,
        "safety": {
            "automatic_publish": False,
            "explicit_confirmation_required": "PUBLICAR"
        },
        "pages": ["/listing-engine", "/listing-engine/sql", "/product-master"]
    }


# ==========================================================
# SPRINT 20 - UPLOAD MANAGER + SUPABASE STORAGE
# Upload server-side, URL pública, validação de imagem e modo automático.
# ==========================================================

from api.core.config import (
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_STORAGE_BUCKET,
    MAX_IMAGE_MB,
)

S20_ALLOWED_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def s20_safe_filename(filename):
    import re as _re

    filename = os.path.basename(str(filename or "image"))
    stem, ext = os.path.splitext(filename)
    safe_stem = _re.sub(r"[^a-zA-Z0-9_-]+", "-", stem).strip("-") or "image"
    return safe_stem[:80], ext.lower()


def s20_public_url(bucket, object_path):
    return (
        f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/"
        f"{quote(bucket, safe='-_')}/{quote(object_path, safe='/-_.')}"
    )


async def s20_upload_bytes(bucket, object_path, data, content_type):
    import httpx

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return {
            "success": False,
            "status_code": 0,
            "error": "SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY não configurada."
        }

    upload_url = (
        f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/"
        f"{quote(bucket, safe='-_')}/{quote(object_path, safe='/-_.')}"
    )
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": content_type,
        "x-upsert": "true",
        "cache-control": "3600",
    }

    try:
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            response = await client.put(upload_url, headers=headers, content=data)

        raw = response.text
        try:
            parsed = response.json()
        except Exception:
            parsed = raw

        return {
            "success": 200 <= response.status_code < 300,
            "status_code": response.status_code,
            "data": parsed,
            "raw": raw[:2000],
            "public_url": s20_public_url(bucket, object_path),
        }
    except Exception as exc:
        return {
            "success": False,
            "status_code": 0,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


async def s20_check_public_image(url):
    import httpx

    if not str(url or "").lower().startswith(("https://", "http://")):
        return {"success": False, "error": "URL não pública."}

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "CommerceHub-Image-Validator/1.0"})

        content_type = str(response.headers.get("content-type") or "").split(";")[0].lower()
        return {
            "success": 200 <= response.status_code < 300 and content_type.startswith("image/"),
            "status_code": response.status_code,
            "content_type": content_type,
            "content_length": len(response.content),
            "error": "" if content_type.startswith("image/") else "O endereço não retornou um arquivo de imagem.",
        }
    except Exception as exc:
        return {
            "success": False,
            "status_code": 0,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


@app.post("/api/storage/products/{product_id}/upload")
async def storage_product_upload(
    product_id: str,
    file: UploadFile = File(...),
    alt_text: str = Form(""),
    position: int = Form(0),
    is_main: str = Form(""),
):
    try:
        product = await s18_get_product(product_id)
        if not product:
            return JSONResponse(status_code=404, content={"success": False, "error": "Produto não encontrado."})

        content_type = str(file.content_type or "").lower().strip()
        if content_type not in S20_ALLOWED_MIME:
            return JSONResponse(status_code=415, content={
                "success": False,
                "error": "Formato inválido. Use JPG, PNG ou WEBP.",
                "content_type": content_type,
            })

        data = await file.read()
        max_bytes = MAX_IMAGE_MB * 1024 * 1024
        if not data:
            return JSONResponse(status_code=400, content={"success": False, "error": "Arquivo vazio."})
        if len(data) > max_bytes:
            return JSONResponse(status_code=413, content={
                "success": False,
                "error": f"Imagem excede o limite de {MAX_IMAGE_MB} MB.",
                "size_bytes": len(data),
            })

        stem, _ = s20_safe_filename(file.filename)
        extension = S20_ALLOWED_MIME[content_type]
        file_hash = hashlib.sha256(data).hexdigest()
        object_name = f"{stem}-{file_hash[:12]}{extension}"
        object_path = f"{DEFAULT_COMPANY_ID}/{product_id}/{object_name}"

        uploaded = await s20_upload_bytes(
            SUPABASE_STORAGE_BUCKET,
            object_path,
            data,
            content_type,
        )
        if not uploaded.get("success"):
            return JSONResponse(status_code=400, content={
                "success": False,
                "error": "Falha ao enviar a imagem ao Supabase Storage.",
                "storage": uploaded,
            })

        public_url = uploaded["public_url"]
        public_check = await s20_check_public_image(public_url)
        main_flag = str(is_main or "").lower() == "true"

        if main_flag:
            await store.update(
                "product_images",
                f"product_id=eq.{quote(product_id, safe='-')}&deleted_at=is.null",
                {"is_main": False},
            )

        image_payload = {
            "company_id": DEFAULT_COMPANY_ID,
            "product_id": product_id,
            "url": public_url,
            "position": s19int(position, 0),
            "is_main": main_flag,
            "alt_text": str(alt_text or "").strip() or None,
            "source": "supabase_storage",
            "hash": file_hash,
            "storage_bucket": SUPABASE_STORAGE_BUCKET,
            "storage_path": object_path,
            "file_name": str(file.filename or object_name),
            "mime_type": content_type,
            "file_size": len(data),
            "upload_status": "ready",
            "validation_status": "valid" if public_check.get("success") else "pending",
            "validation_message": public_check.get("error") or None,
        }

        saved = await store.insert("product_images", image_payload)
        if not saved.get("success"):
            return JSONResponse(status_code=400, content={
                "success": False,
                "error": "Imagem enviada ao Storage, mas não gravada no Product Master.",
                "public_url": public_url,
                "database": saved,
            })

        if main_flag or not product.get("primary_image_url"):
            await store.update(
                "products",
                f"id=eq.{quote(product_id, safe='-')}",
                {"primary_image_url": public_url, "sync_status": "pending"},
            )

        await s18_history(
            product_id,
            "storage_image_uploaded",
            f"Imagem {file.filename} enviada ao Supabase Storage.",
            payload={"public_url": public_url, "storage_path": object_path, "is_main": main_flag},
        )
        return RedirectResponse(f"/product-master/{product_id}/images", status_code=303)

    except Exception as exc:
        return JSONResponse(status_code=500, content={
            "success": False,
            "version": APP_VERSION,
            "error": "Falha interna no upload.",
            "error_type": type(exc).__name__,
            "detail": str(exc),
            "product_id": product_id,
        })


@app.get("/api/storage/products/{product_id}/validate")
async def storage_validate_product_images(product_id: str):
    result = await store.select(
        "product_images",
        f"select=*&product_id=eq.{quote(product_id, safe='-')}&order=position.asc"
    )
    images = result.get("data") or []
    validations = []

    for image in images:
        check = await s20_check_public_image(image.get("url"))
        validations.append({
            "id": image.get("id"),
            "url": image.get("url"),
            "is_main": image.get("is_main"),
            **check,
        })

    return {
        "success": bool(images) and all(item.get("success") for item in validations),
        "version": APP_VERSION,
        "product_id": product_id,
        "count": len(images),
        "validations": validations,
    }


@app.get("/upload-manager", response_class=HTMLResponse)
async def upload_manager_page():
    images_result = await store.select(
        "product_images",
        "select=*&source=eq.supabase_storage&order=created_at.desc&limit=100"
    )
    images = images_result.get("data") or []

    total_bytes = sum(int(i.get("file_size") or 0) for i in images)
    rows = "".join(
        f"""<tr>
<td><img src='{s19e(i.get("url"))}' style='width:64px;height:64px;object-fit:contain'></td>
<td>{s19e(i.get("file_name") or '-')}</td>
<td>{s19e(i.get("mime_type") or '-')}</td>
<td>{s19e(i.get("file_size") or 0)}</td>
<td>{s19e(i.get("storage_path") or '-')}</td>
<td><a class='btn' href='{s19e(i.get("url"))}' target='_blank'>Abrir</a></td>
</tr>"""
        for i in images
    ) or "<tr><td colspan='6'>Nenhum upload realizado.</td></tr>"

    content = f"""
<div class='grid'>
<div class='metric'><span>Uploads</span><strong>{len(images)}</strong></div>
<div class='metric'><span>Armazenamento</span><strong>{round(total_bytes / 1024 / 1024, 2)} MB</strong></div>
<div class='metric'><span>Bucket</span><strong>{s19e(SUPABASE_STORAGE_BUCKET)}</strong></div>
<div class='metric'><span>Limite</span><strong>{MAX_IMAGE_MB} MB/imagem</strong></div>
</div>
<div class='card'>
<h2>Upload Manager</h2>
<p>Envie imagens pela página do produto. O CommerceHub cria uma URL pública compatível com o Mercado Livre.</p>
<a class='btn' href='/product-master'>Abrir Product Master</a>
<a class='btn' href='/upload-manager/sql'>SQL Sprint 20</a>
<a class='btn' href='/api/upload-manager/status'>Status do módulo</a>
</div>
<div class='card'>
<table>
<thead><tr><th>Imagem</th><th>Arquivo</th><th>Tipo</th><th>Bytes</th><th>Caminho</th><th>Ação</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>
"""
    return HTMLResponse(shell("Upload Manager", content))


@app.get("/upload-manager/sql", response_class=HTMLResponse)
async def upload_manager_sql_page():
    sql_text = open("sprint20_upload_manager.sql", "r", encoding="utf-8").read()
    return HTMLResponse(shell(
        "SQL Sprint 20",
        f"<div class='card'><h2>Migration Upload Manager</h2><p>Copie e execute no Supabase SQL Editor.</p><pre>{s19e(sql_text)}</pre></div>"
    ))


async def s20_get_automation_setting():
    result = await store.select(
        "settings",
        f"select=*&company_id=eq.{DEFAULT_COMPANY_ID}&key=eq.listing_automation&limit=1"
    )
    rows = result.get("data") or []
    if not rows:
        return {"enabled": False, "mode": "manual", "max_per_run": 10}
    return rows[0].get("value") or {"enabled": False, "mode": "manual", "max_per_run": 10}


@app.get("/listing-automation", response_class=HTMLResponse)
async def listing_automation_page():
    setting = await s20_get_automation_setting()
    enabled = bool(setting.get("enabled"))
    content = f"""
<div class='grid'>
<div class='metric'><span>Modo atual</span><strong>{'AUTOMÁTICO' if enabled else 'MANUAL'}</strong></div>
<div class='metric'><span>Publicação manual</span><strong>Disponível</strong></div>
<div class='metric'><span>Automação</span><strong>{'Ativa' if enabled else 'Desativada'}</strong></div>
<div class='metric'><span>Máximo por execução</span><strong>{s19e(setting.get('max_per_run', 10))}</strong></div>
</div>
<div class='card'>
<h2>Modos de publicação</h2>
<p><b>Publicar agora:</b> permanece disponível em cada anúncio.</p>
<p><b>Publicação automática:</b> publica somente rascunhos marcados como automáticos e aprovados na validação.</p>
<form method='post' action='/api/listing-engine/automation/settings'>
<label><input type='checkbox' name='enabled' value='true' style='width:auto' {'checked' if enabled else ''}> Ativar publicação automática global</label><br><br>
<label>Máximo de anúncios por execução</label>
<input name='max_per_run' value='{s19e(setting.get("max_per_run", 10))}'>
<button type='submit'>Salvar automação</button>
</form>
</div>
<div class='card'>
<form method='post' action='/api/listing-engine/automation/run'>
<button type='submit'>Executar automação agora</button>
</form>
<p>A execução agendada contínua poderá ser conectada ao Vercel Cron em uma etapa posterior.</p>
</div>
"""
    return HTMLResponse(shell("Automação de Publicações", content))


@app.post("/api/listing-engine/automation/settings")
async def listing_automation_settings(request: Request):
    form = await request.form()
    enabled = str(form.get("enabled") or "").lower() == "true"
    max_per_run = max(1, min(100, s19int(form.get("max_per_run"), 10)))
    value = {
        "enabled": enabled,
        "mode": "automatic" if enabled else "manual",
        "max_per_run": max_per_run,
    }

    result = await store.upsert("settings", {
        "company_id": DEFAULT_COMPANY_ID,
        "key": "listing_automation",
        "value": value,
    }, "company_id,key")

    if not result.get("success"):
        return JSONResponse(status_code=400, content={"success": False, "error": result.get("error") or result.get("raw")})
    return RedirectResponse("/listing-automation", status_code=303)


@app.post("/api/listing-engine/{listing_id}/automatic")
async def listing_toggle_automatic(listing_id: str, request: Request):
    listing = await s19_get_listing(listing_id)
    if not listing:
        return JSONResponse(status_code=404, content={"success": False, "error": "Anúncio não encontrado."})

    form = await request.form()
    enabled = str(form.get("enabled") or "").lower() == "true"
    updated = await store.update(
        "listings",
        f"id=eq.{quote(listing_id, safe='-')}",
        {"auto_publish": enabled},
    )
    if not updated.get("success"):
        return JSONResponse(status_code=400, content={"success": False, "error": updated.get("error") or updated.get("raw")})

    await s19_history(
        listing_id,
        listing.get("product_id"),
        "automatic_mode_changed",
        f"Publicação automática {'ativada' if enabled else 'desativada'}.",
        listing.get("status"),
        listing.get("status"),
        {"auto_publish": enabled},
    )
    return RedirectResponse(f"/listing-engine/{listing_id}", status_code=303)


async def s20_publish_automatic_listing(listing):
    listing_id = listing.get("id")
    context = await s19_product_context(listing.get("product_id"))
    validation = s19_local_validation(context, listing)

    if not validation.get("valid"):
        await store.update(
            "listings",
            f"id=eq.{quote(str(listing_id), safe='-')}",
            {
                "validation_status": "failed",
                "last_error": json.dumps(validation, ensure_ascii=False),
                "auto_publish_last_attempt": __import__("datetime").datetime.utcnow().isoformat(),
                "auto_publish_attempts": int(listing.get("auto_publish_attempts") or 0) + 1,
            },
        )
        return {"success": False, "listing_id": listing_id, "stage": "validation", "validation": validation}

    # Confirma que todas as URLs realmente retornam imagens públicas.
    image_checks = []
    for url in context.get("images") or []:
        image_checks.append(await s20_check_public_image(url))
    if not image_checks or not all(check.get("success") for check in image_checks):
        return {
            "success": False,
            "listing_id": listing_id,
            "stage": "images",
            "error": "Uma ou mais imagens não são públicas ou válidas.",
            "image_checks": image_checks,
        }

    publish_attempt = await s202_publish_with_fallback(context, listing)
    payload = publish_attempt.get("payload") or {}
    result = publish_attempt.get("result") or {}
    if not publish_attempt.get("success"):
        await store.update(
            "listings",
            f"id=eq.{quote(str(listing_id), safe='-')}",
            {
                "validation_status": "failed",
                "last_error": str(result.get("error") or result.get("raw") or result.get("data"))[:3000],
                "auto_publish_last_attempt": __import__("datetime").datetime.utcnow().isoformat(),
                "auto_publish_attempts": int(listing.get("auto_publish_attempts") or 0) + 1,
            },
        )
        return {"success": False, "listing_id": listing_id, "stage": "mercado_livre", "result": result}

    item = result.get("data") or {}
    external_id = item.get("id")
    new_status = item.get("status") or "active"
    permalink = item.get("permalink")

    await store.update(
        "listings",
        f"id=eq.{quote(str(listing_id), safe='-')}",
        {
            "external_id": external_id,
            "permalink": permalink,
            "item_url": permalink,
            "status": new_status,
            "validation_status": "published",
            "last_error": None,
            "payload": payload,
            "published_at": __import__("datetime").datetime.utcnow().isoformat(),
            "last_synced_at": __import__("datetime").datetime.utcnow().isoformat(),
            "auto_publish_last_attempt": __import__("datetime").datetime.utcnow().isoformat(),
            "auto_publish_attempts": int(listing.get("auto_publish_attempts") or 0) + 1,
        },
    )

    description = str(listing.get("description") or "").strip()
    if external_id and description:
        await ml_request(
            f"/items/{external_id}/description",
            method="POST",
            payload={"plain_text": description},
        )

    await store.update(
        "products",
        f"id=eq.{quote(str(listing.get('product_id')), safe='-')}",
        {"sync_status": "synced", "last_synced_at": __import__("datetime").datetime.utcnow().isoformat()},
    )
    await s19_history(
        listing_id,
        listing.get("product_id"),
        "auto_published",
        f"Anúncio {external_id} publicado automaticamente.",
        listing.get("status"),
        new_status,
        {"external_id": external_id},
    )
    return {"success": True, "listing_id": listing_id, "external_id": external_id, "permalink": permalink}


@app.post("/api/listing-engine/automation/run")
async def listing_automation_run():
    setting = await s20_get_automation_setting()
    if not setting.get("enabled"):
        return JSONResponse(status_code=409, content={
            "success": False,
            "error": "A publicação automática global está desativada.",
            "next": "/listing-automation",
        })

    max_per_run = max(1, min(100, s19int(setting.get("max_per_run"), 10)))
    result = await store.select(
        "listings",
        "select=*&company_id=eq."
        + quote(DEFAULT_COMPANY_ID, safe="-")
        + "&marketplace=eq.mercado_livre"
        + "&auto_publish=eq.true"
        + "&external_id=is.null"
        + "&status=eq.draft"
        + f"&order=created_at.asc&limit={max_per_run}"
    )
    listings = result.get("data") or []
    processed = []

    for listing in listings:
        processed.append(await s20_publish_automatic_listing(listing))

    return {
        "success": all(item.get("success") for item in processed) if processed else True,
        "version": APP_VERSION,
        "mode": "automatic",
        "selected": len(listings),
        "published": sum(1 for item in processed if item.get("success")),
        "failed": sum(1 for item in processed if not item.get("success")),
        "results": processed,
    }


@app.get("/api/upload-manager/status")
async def upload_manager_status():
    checks = {}
    for table in ["product_images", "products", "listings", "settings"]:
        result = await store.select(table, "select=*&limit=1")
        checks[table] = {
            "success": bool(result.get("success")),
            "status_code": result.get("status_code"),
            "rows": len(result.get("data") or []),
            "error": str(result.get("error") or result.get("raw") or "")[:500],
        }

    bucket_url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_STORAGE_BUCKET}/" if SUPABASE_URL else ""
    return {
        "success": all(item["success"] for item in checks.values())
                   and bool(SUPABASE_URL)
                   and bool(SUPABASE_SERVICE_ROLE_KEY),
        "version": APP_VERSION,
        "module": "upload_manager_supabase_storage",
        "bucket": SUPABASE_STORAGE_BUCKET,
        "bucket_public_base_url": bucket_url,
        "max_image_mb": MAX_IMAGE_MB,
        "allowed_mime_types": sorted(S20_ALLOWED_MIME.keys()),
        "service_role_configured": bool(SUPABASE_SERVICE_ROLE_KEY),
        "checks": checks,
        "pages": ["/upload-manager", "/upload-manager/sql", "/listing-automation"],
    }


# ==========================================================
# SPRINT 20.1 - IMAGE MANAGER ENTERPRISE
# Excluir, principal, ordenar e limpar registros inválidos.
# ==========================================================

async def s201_get_image(image_id):
    result = await store.select(
        "product_images",
        f"select=*&id=eq.{quote(str(image_id), safe='-')}&limit=1"
    )
    rows = result.get("data") or []
    return rows[0] if rows else None


async def s201_delete_storage_object(bucket, object_path):
    import httpx
    if not bucket or not object_path:
        return {"success": True, "skipped": True}

    url = (
        f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/"
        f"{quote(str(bucket), safe='-_')}/{quote(str(object_path), safe='/-_.')}"
    )
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(url, headers=headers)
        return {
            "success": response.status_code in [200, 204, 404],
            "status_code": response.status_code,
            "raw": response.text[:1000],
        }
    except Exception as exc:
        return {"success": False, "error_type": type(exc).__name__, "error": str(exc)}


async def s201_refresh_primary(product_id):
    result = await store.select(
        "product_images",
        f"select=*&product_id=eq.{quote(str(product_id), safe='-')}&deleted_at=is.null&order=is_main.desc,position.asc,created_at.asc&limit=1"
    )
    rows = result.get("data") or []
    primary_url = rows[0].get("url") if rows else None
    if rows and not rows[0].get("is_main"):
        await store.update(
            "product_images",
            f"id=eq.{quote(str(rows[0].get('id')), safe='-')}",
            {"is_main": True},
        )
    await store.update(
        "products",
        f"id=eq.{quote(str(product_id), safe='-')}",
        {"primary_image_url": primary_url, "sync_status": "pending"},
    )
    return primary_url


@app.post("/api/image-manager/{image_id}/main")
async def image_manager_set_main(image_id: str):
    image = await s201_get_image(image_id)
    if not image:
        return JSONResponse(status_code=404, content={"success": False, "error": "Imagem não encontrada."})

    product_id = image.get("product_id")
    await store.update(
        "product_images",
        f"product_id=eq.{quote(str(product_id), safe='-')}&deleted_at=is.null",
        {"is_main": False},
    )
    updated = await store.update(
        "product_images",
        f"id=eq.{quote(image_id, safe='-')}",
        {"is_main": True},
    )
    await store.update(
        "products",
        f"id=eq.{quote(str(product_id), safe='-')}",
        {"primary_image_url": image.get("url"), "sync_status": "pending"},
    )
    await s18_history(product_id, "main_image_changed", "Imagem principal alterada.", payload={"image_id": image_id})
    return RedirectResponse(f"/product-master/{product_id}/images", status_code=303)


@app.post("/api/image-manager/{image_id}/move")
async def image_manager_move(image_id: str, request: Request):
    image = await s201_get_image(image_id)
    if not image:
        return JSONResponse(status_code=404, content={"success": False, "error": "Imagem não encontrada."})

    form = await request.form()
    direction = str(form.get("direction") or "up")
    current_position = int(image.get("position") or 0)
    new_position = max(0, current_position - 1) if direction == "up" else current_position + 1

    await store.update(
        "product_images",
        f"id=eq.{quote(image_id, safe='-')}",
        {"position": new_position},
    )
    await s18_history(
        image.get("product_id"),
        "image_reordered",
        f"Imagem movida para posição {new_position}.",
        payload={"image_id": image_id, "old_position": current_position, "new_position": new_position},
    )
    return RedirectResponse(f"/product-master/{image.get('product_id')}/images", status_code=303)


@app.post("/api/image-manager/{image_id}/delete")
async def image_manager_delete(image_id: str):
    image = await s201_get_image(image_id)
    if not image:
        return JSONResponse(status_code=404, content={"success": False, "error": "Imagem não encontrada."})

    product_id = image.get("product_id")
    storage_result = await s201_delete_storage_object(
        image.get("storage_bucket"),
        image.get("storage_path"),
    )

    deleted = await store.delete(
        "product_images",
        f"id=eq.{quote(image_id, safe='-')}",
    )
    if not deleted.get("success"):
        return JSONResponse(status_code=400, content={
            "success": False,
            "error": "Não foi possível remover o registro da imagem.",
            "database": deleted,
            "storage": storage_result,
        })

    new_primary = await s201_refresh_primary(product_id)
    await s18_history(
        product_id,
        "image_deleted",
        "Imagem removida do Product Master.",
        payload={
            "image_id": image_id,
            "url": image.get("url"),
            "storage_result": storage_result,
            "new_primary": new_primary,
        },
    )
    return RedirectResponse(f"/product-master/{product_id}/images", status_code=303)


@app.post("/api/image-manager/products/{product_id}/remove-invalid")
async def image_manager_remove_invalid(product_id: str):
    result = await store.select(
        "product_images",
        f"select=*&product_id=eq.{quote(product_id, safe='-')}"
    )
    images = result.get("data") or []
    removed = []
    for image in images:
        url = str(image.get("url") or "")
        if not url.lower().startswith(("http://", "https://")):
            await store.delete("product_images", f"id=eq.{quote(str(image.get('id')), safe='-')}")
            removed.append(image.get("id"))
    await s201_refresh_primary(product_id)
    return {
        "success": True,
        "version": APP_VERSION,
        "product_id": product_id,
        "removed_count": len(removed),
        "removed_ids": removed,
    }


@app.get("/api/image-manager/status")
async def image_manager_status():
    result = await store.select("product_images", "select=*&limit=200")
    images = result.get("data") or []
    local_paths = [
        i for i in images
        if not str(i.get("url") or "").lower().startswith(("http://", "https://"))
    ]
    storage_images = [i for i in images if i.get("source") == "supabase_storage"]
    return {
        "success": True,
        "version": APP_VERSION,
        "module": "image_manager_enterprise",
        "counts": {
            "images_checked": len(images),
            "storage_images": len(storage_images),
            "invalid_or_local_paths": len(local_paths),
        },
        "features": [
            "upload",
            "delete_database",
            "delete_storage",
            "set_main",
            "move_up",
            "move_down",
            "copy_public_url",
            "validate_public_image",
        ],
        "pages": ["/upload-manager", "/product-master"],
    }


@app.get("/api/listing-engine/{listing_id}/readiness")
async def listing_readiness(listing_id: str):
    listing = await s19_get_listing(listing_id)
    if not listing:
        return JSONResponse(status_code=404, content={"success": False, "error": "Anúncio não encontrado."})

    context = await s19_product_context(listing.get("product_id"))
    if not context:
        return JSONResponse(status_code=404, content={"success": False, "error": "Produto relacionado não encontrado."})

    validation = s19_local_validation(context, listing)
    image_checks = []
    for url in context.get("images") or []:
        image_checks.append(await s20_check_public_image(url))

    missing = []
    product = context["product"]

    if not listing.get("category_id"):
        missing.append("category_id")
    if not product.get("ean"):
        missing.append("GTIN/EAN")
    if not product.get("brand"):
        missing.append("BRAND")
    if not context.get("images"):
        missing.append("pictures")
    if str(product.get("internal_status") or "") != "ready":
        missing.append("product_internal_status_ready")

    public_images_ok = bool(image_checks) and all(item.get("success") for item in image_checks)

    return {
        "success": validation.get("valid") and public_images_ok,
        "version": APP_VERSION,
        "listing_id": listing_id,
        "ready_to_publish": validation.get("valid") and public_images_ok,
        "recommended_mode": "user_product",
        "validation": validation,
        "public_images_ok": public_images_ok,
        "image_checks": image_checks,
        "missing_or_warning": missing,
    }


# ==========================================================
# SPRINT 21 - SMART CATEGORY ENGINE
# ==========================================================

def s21_required(tags):
    tags = tags or {}
    return bool(tags.get("required") or tags.get("catalog_required") or tags.get("catalog_listing_required"))

async def s21_sync_category(category_id):
    category_id = str(category_id or "").strip()
    category = await ml_request(f"/categories/{quote(category_id, safe='-_')}")
    attrs = await ml_request(f"/categories/{quote(category_id, safe='-_')}/attributes")
    if not category.get("success") or not attrs.get("success"):
        return {"success": False, "category": category, "attributes": attrs}
    c = category.get("data") or {}
    saved = await store.upsert("ml_categories", {
        "id": category_id, "site_id": c.get("site_id") or "MLB", "name": c.get("name") or category_id,
        "path": c.get("path_from_root") or [], "settings": c.get("settings") or {}, "raw_data": c,
        "last_synced_at": __import__("datetime").datetime.utcnow().isoformat()
    }, "id")
    if not saved.get("success"):
        return {"success": False, "stage": "save_category", "result": saved}
    total=0; errors=[]
    for a in (attrs.get("data") or []):
        tags=a.get("tags") or {}
        r=await store.upsert("ml_category_attributes", {
            "category_id": category_id, "attribute_id": a.get("id"), "name": a.get("name") or a.get("id"),
            "value_type": a.get("value_type"), "tags": tags, "values": a.get("values") or [],
            "required": s21_required(tags), "catalog_required": bool(tags.get("catalog_required") or tags.get("catalog_listing_required")),
            "raw_data": a, "last_synced_at": __import__("datetime").datetime.utcnow().isoformat()
        }, "category_id,attribute_id")
        if r.get("success"): total+=1
        else: errors.append({"attribute_id":a.get("id"),"error":r.get("error") or r.get("raw")})
    return {"success": not errors, "category_id":category_id, "category_name":c.get("name"), "saved":total, "errors":errors}

async def s21_category_attrs(category_id):
    r=await store.select("ml_category_attributes", "select=*&category_id=eq."+quote(str(category_id),safe='-_')+"&order=required.desc,name.asc")
    return r.get("data") or []

async def s21_product_values(product_id, category_id):
    r=await store.select("product_marketplace_attributes", "select=*&product_id=eq."+quote(str(product_id),safe='-')+"&marketplace=eq.mercado_livre&category_id=eq."+quote(str(category_id),safe='-_'))
    return {str(x.get("attribute_id")):x for x in (r.get("data") or [])}

def s21_guess(attr_id, attr_name, product, attrs):
    aid=str(attr_id or '').upper(); name=str(attr_name or '').lower()
    if aid=='BRAND': return product.get('brand'),'product.brand',100
    if aid=='GTIN': return product.get('ean'),'product.ean',100
    for x in attrs:
        k=str(x.get('name') or '').lower()
        if (aid=='MODEL' and k in ['modelo','model']) or (aid in ['COLOR','MAIN_COLOR'] and k in ['cor','color']) or k==name:
            return x.get('value'),'product_attribute',100
    if aid=='MODEL':
        v=str(product.get('seo_name') or product.get('name') or '').strip()[:60]
        return (v or None),'product.name',65
    return None,None,0

async def s21_prepare(product_id, category_id):
    await s21_sync_category(category_id)
    context=await s19_product_context(product_id)
    if not context: return {"success":False,"error":"Produto não encontrado"}
    values=await s21_product_values(product_id,category_id)
    result=[]
    for a in await s21_category_attrs(category_id):
        aid=str(a.get('attribute_id')); current=values.get(aid)

        # Se o usuário informou um motivo válido de ausência de GTIN,
        # não volte a sugerir automaticamente o EAN inválido do fornecedor.
        empty_reason = values.get('EMPTY_GTIN_REASON') or values.get('empty_gtin_reason') or {}
        if str(aid).upper() == 'GTIN' and (
            empty_reason.get('value_id') or empty_reason.get('value_name')
        ):
            result.append({
                "attribute_id": aid,
                "name": a.get('name'),
                "required": a.get('required') or a.get('catalog_required'),
                "value_name": None,
                "source": "gtin_resolver",
                "status": "not_applicable"
            })
            continue

        if current and current.get('value_name'):
            result.append({"attribute_id":aid,"name":a.get('name'),"required":a.get('required') or a.get('catalog_required'),"value_name":current.get('value_name'),"source":current.get('source'),"status":"filled"}); continue
        val,src,conf=s21_guess(aid,a.get('name'),context['product'],context['attributes'])
        if val:
            await store.upsert("product_marketplace_attributes", {"company_id":DEFAULT_COMPANY_ID,"product_id":product_id,"marketplace":"mercado_livre","category_id":category_id,"attribute_id":aid,"value_name":val,"source":src,"confidence":conf,"status":"active","raw_data":{}}, "product_id,marketplace,attribute_id")
        result.append({"attribute_id":aid,"name":a.get('name'),"required":a.get('required') or a.get('catalog_required'),"value_name":val,"source":src,"status":"suggested" if val else "missing"})
    return {"success":True,"product_id":product_id,"category_id":category_id,"attributes":result}

async def s21_validation(product_id, category_id):
    return await s212_attribute_validation(product_id, category_id)

async def s21_payload_attributes(product_id, category_id, base):
    return await s212_payload_attributes(product_id, category_id, base)

@app.get('/smart-category-engine', response_class=HTMLResponse)
async def smart_category_engine_page():
    return HTMLResponse(shell('Smart Category Engine', """<div class='card'><h2>Smart Category Engine</h2><form method='get' action='/smart-category-engine/category'><label>Categoria ML</label><input name='category_id' value='MLB1648' required><button type='submit'>Consultar e salvar exigências</button></form></div>"""))

@app.get('/smart-category-engine/category', response_class=HTMLResponse)
async def smart_category_category_page(category_id:str):
    sync=await s21_sync_category(category_id); attrs=await s21_category_attrs(category_id)
    rows=''.join(f"<tr><td>{s19e(a.get('attribute_id'))}</td><td>{s19e(a.get('name'))}</td><td>{'Sim' if a.get('required') else 'Não'}</td><td>{'Sim' if a.get('catalog_required') else 'Não'}</td><td>{s19e(a.get('value_type') or '-')}</td></tr>" for a in attrs) or "<tr><td colspan='5'>Nenhum atributo.</td></tr>"
    return HTMLResponse(shell('Categoria '+category_id, f"<div class='card'><h2>{s19e(category_id)}</h2><p>Sincronização: {'OK' if sync.get('success') else 'ERRO'}</p><table><thead><tr><th>ID</th><th>Nome</th><th>Obrigatório</th><th>Catálogo</th><th>Tipo</th></tr></thead><tbody>{rows}</tbody></table></div>"))

@app.get('/smart-category-engine/product/{product_id}/category/{category_id}', response_class=HTMLResponse)
async def smart_category_product_page(product_id:str, category_id:str):
    await s21_prepare(product_id, category_id)
    attrs = await s21_category_attrs(category_id)
    vals = await s21_product_values(product_id, category_id)
    validation = await s21_validation(product_id, category_id)

    rows = ''
    for attr in attrs:
        aid = str(attr.get('attribute_id') or '').upper()
        current = vals.get(aid) or vals.get(aid.lower()) or {}
        current_value = current.get('value_name') or ''
        current_value_id = current.get('value_id') or ''
        required = bool(attr.get('required') or attr.get('catalog_required'))
        allowed = attr.get('values') or []

        field_html = ''
        if allowed:
            options = ["<option value=''>Selecione...</option>"]
            for option in allowed:
                option_id = str(option.get('id') or '')
                option_name = str(option.get('name') or option_id)
                selected = (
                    current_value_id == option_id
                    or current_value.lower() == option_name.lower()
                    or current_value.lower() == option_id.lower()
                )
                options.append(
                    f"<option value='{s19e(option_name)}' data-value-id='{s19e(option_id)}' {'selected' if selected else ''}>{s19e(option_name)}</option>"
                )
            field_html = f"<select name='value_name' style='width:100%;padding:9px'>{''.join(options)}</select>"
        else:
            field_html = f"<input name='value_name' value='{s19e(current_value)}' style='width:100%'>"

        hint = ''
        if aid == 'GTIN':
            hint = "<small>Use GTIN real de 8, 12, 13 ou 14 dígitos. Não escreva EMPTY_GTIN_REASON aqui.</small>"
        elif aid == 'EMPTY_GTIN_REASON':
            hint = "<small>Preencha somente quando o produto realmente não possuir GTIN.</small>"

        status = 'OK'
        if aid == 'GTIN' and current_value and not s212_valid_gtin(current_value):
            status = 'INVÁLIDO'
        elif required and not current_value and not current_value_id:
            status = 'PENDENTE'

        rows += f"""
<tr>
<td>{s19e(aid)}</td>
<td>{s19e(attr.get('name'))}</td>
<td>{'Obrigatório' if required else 'Opcional'}</td>
<td>
<form method='post' action='/api/smart-category/product/{product_id}/attribute'>
<input type='hidden' name='category_id' value='{s19e(category_id)}'>
<input type='hidden' name='attribute_id' value='{s19e(aid)}'>
{field_html}
{hint}
<button type='submit'>Salvar</button>
</form>
</td>
<td>{s19e(current.get('source') or '-')}</td>
<td>{status}</td>
</tr>
"""

    missing_html = ''.join(
        f"<li>{s19e(item.get('attribute_id'))}: {s19e(item.get('message') or item.get('name') or 'Campo obrigatório')}</li>"
        for item in validation.get('missing', [])
    ) or "<li>Nenhum atributo obrigatório faltando.</li>"

    invalid_html = ''.join(
        f"<li>{s19e(item.get('attribute_id'))}: {s19e(item.get('message'))}</li>"
        for item in validation.get('invalid', [])
    ) or "<li>Nenhum atributo inválido.</li>"

    content = f"""
<div class='grid'>
<div class='metric'><span>Obrigatórios</span><strong>{validation.get('required_count')}</strong></div>
<div class='metric'><span>Faltando</span><strong>{validation.get('missing_count')}</strong></div>
<div class='metric'><span>Inválidos</span><strong>{validation.get('invalid_count')}</strong></div>
<div class='metric'><span>Pronto</span><strong>{'SIM' if validation.get('valid') else 'NÃO'}</strong></div>
</div>
<div class='card'>
<a class='btn' href='/api/smart-category/product/{product_id}/category/{category_id}/validate'>Validar requisitos</a>
<a class='btn' href='/product-master/{product_id}/listing'>Voltar ao anúncio</a>
<a class='btn' href='/product-master/{product_id}/edit'>Editar produto</a>
<a class='btn' href='/gtin-resolver/product/{product_id}/category/{category_id}'>Resolver GTIN</a>
</div>
<div class='card'>
<h2>Pendências</h2>
<ul>{missing_html}</ul>
<h2>Valores inválidos</h2>
<ul>{invalid_html}</ul>
</div>
<div class='card'>
<table>
<thead><tr><th>ID</th><th>Atributo</th><th>Exigência</th><th>Valor</th><th>Origem</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>
"""
    return HTMLResponse(shell('Atributos inteligentes', content))

@app.post('/api/smart-category/product/{product_id}/attribute')
async def smart_category_save_attribute(product_id:str, request:Request):
    f=await request.form(); cid=str(f.get('category_id') or '').strip(); aid=str(f.get('attribute_id') or '').strip(); val=str(f.get('value_name') or '').strip()
    metadata = await s22_gtin_metadata(cid)
    attr_meta = (
        metadata.get('empty_reason')
        if aid.upper() == 'EMPTY_GTIN_REASON'
        else metadata.get('gtin')
        if aid.upper() == 'GTIN'
        else None
    )
    normalized = s212_value_payload(aid, None, val or None, attr_meta)
    value_id = normalized.get('value_id') if normalized else None
    value_name = normalized.get('value_name') if normalized else None

    r=await store.upsert('product_marketplace_attributes', {
        "company_id":DEFAULT_COMPANY_ID,
        "product_id":product_id,
        "marketplace":"mercado_livre",
        "category_id":cid,
        "attribute_id":aid,
        "value_id":value_id,
        "value_name":value_name,
        "source":"manual",
        "confidence":100,
        "status":"active",
        "raw_data":{}
    }, 'product_id,marketplace,attribute_id')

    if not r.get('success'):
        return JSONResponse(status_code=400,content={"success":False,"error":r.get('error') or r.get('raw')})

    if aid.upper() == 'EMPTY_GTIN_REASON' and (value_id or value_name):
        await s22_delete_attribute_value(product_id, 'GTIN')
        await store.update(
            'products',
            f"id=eq.{quote(str(product_id), safe='-')}",
            {"ean": None, "sync_status": "pending"}
        )
    elif aid.upper() == 'GTIN' and s212_valid_gtin(value_name):
        await s22_delete_attribute_value(product_id, 'EMPTY_GTIN_REASON')
        await store.update(
            'products',
            f"id=eq.{quote(str(product_id), safe='-')}",
            {"ean": s212_digits(value_name), "sync_status": "pending"}
        )
    return RedirectResponse(f'/smart-category-engine/product/{product_id}/category/{cid}',status_code=303)

@app.get('/api/smart-category/category/{category_id}/sync')
async def smart_category_sync(category_id:str): return await s21_sync_category(category_id)

@app.get('/api/smart-category/product/{product_id}/category/{category_id}/validate')
async def smart_category_validate(product_id:str, category_id:str): return {"success":True,"version":APP_VERSION,"validation":await s21_validation(product_id,category_id)}

@app.get('/api/smart-category/status')
async def smart_category_status():
    checks={}
    for table in ['ml_categories','ml_category_attributes','product_marketplace_attributes']:
        r=await store.select(table,'select=*&limit=1'); checks[table]={"success":bool(r.get('success')),"status_code":r.get('status_code'),"rows":len(r.get('data') or []),"error":str(r.get('error') or r.get('raw') or '')[:300]}
    return {"success":all(x['success'] for x in checks.values()),"version":APP_VERSION,"module":"smart_category_engine","checks":checks}


# ==========================================================
# SPRINT 21.2 - INTELLIGENT ATTRIBUTE PAYLOAD
# Valida GTIN, separa EMPTY_GTIN_REASON e usa value_id/value_name.
# ==========================================================

def s212_digits(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def s212_valid_gtin(value):
    digits = s212_digits(value)
    if len(digits) not in (8, 12, 13, 14):
        return False

    body = digits[:-1]
    check_digit = int(digits[-1])
    total = 0
    reverse_body = list(reversed(body))
    for index, char in enumerate(reverse_body):
        weight = 3 if index % 2 == 0 else 1
        total += int(char) * weight

    expected = (10 - (total % 10)) % 10
    return expected == check_digit


def s212_value_payload(attribute_id, value_id=None, value_name=None, metadata=None):
    attribute_id = str(attribute_id or "").strip().upper()
    value_id = str(value_id or "").strip() or None
    value_name = str(value_name or "").strip() or None
    metadata = metadata or {}

    # Nunca use o nome do atributo como se fosse seu valor.
    if value_name and value_name.upper() == attribute_id:
        value_name = None

    allowed_values = metadata.get("values") or []
    if not value_id and value_name and allowed_values:
        for option in allowed_values:
            option_id = str(option.get("id") or "").strip()
            option_name = str(option.get("name") or "").strip()
            if value_name.lower() in {option_id.lower(), option_name.lower()}:
                if option_id:
                    value_id = option_id
                value_name = option_name or value_name
                break

    payload = {"id": attribute_id}
    if value_id:
        payload["value_id"] = value_id
    elif value_name:
        payload["value_name"] = value_name
    else:
        return None
    return payload


async def s212_attribute_metadata(category_id):
    attrs = await s21_category_attrs(category_id)
    return {
        str(attr.get("attribute_id") or "").upper(): attr
        for attr in attrs
        if attr.get("attribute_id")
    }


async def s212_payload_attributes(product_id, category_id, base):
    values = await s21_product_values(product_id, category_id)
    metadata = await s212_attribute_metadata(category_id)

    merged = {}
    valid_gtin = None

    # Primeiro lê os atributos automáticos do Product Master.
    for item in base or []:
        aid = str(item.get("id") or "").strip().upper()
        if not aid:
            continue

        if aid == "GTIN":
            candidate = item.get("value_name") or item.get("value_id")
            if s212_valid_gtin(candidate):
                valid_gtin = s212_digits(candidate)
                merged["GTIN"] = {"id": "GTIN", "value_name": valid_gtin}
            continue

        payload = s212_value_payload(
            aid,
            item.get("value_id"),
            item.get("value_name"),
            metadata.get(aid)
        )
        if payload:
            merged[aid] = payload

    # Depois sobrepõe com os valores salvos no Smart Category Engine.
    for aid, row in values.items():
        aid = str(aid or "").strip().upper()
        if not aid:
            continue

        if aid == "GTIN":
            candidate = row.get("value_name") or row.get("value_id")
            if s212_valid_gtin(candidate):
                valid_gtin = s212_digits(candidate)
                merged["GTIN"] = {"id": "GTIN", "value_name": valid_gtin}
            else:
                merged.pop("GTIN", None)
            continue

        payload = s212_value_payload(
            aid,
            row.get("value_id"),
            row.get("value_name"),
            metadata.get(aid)
        )
        if payload:
            merged[aid] = payload
        else:
            merged.pop(aid, None)

    # GTIN e motivo de ausência são mutuamente exclusivos.
    if valid_gtin:
        merged.pop("EMPTY_GTIN_REASON", None)
    else:
        merged.pop("GTIN", None)

    official_ids = set(metadata.keys())
    internal_prefixes = (
        "CATEGORY_RULE_",
        "COMMERCEHUB_",
        "CH_INTERNAL_",
        "ML_RULE_",
        "SMART_SCORE",
        "LAST_ML_ERROR",
    )

    clean = []
    for attribute_id, payload in merged.items():
        upper_id = str(attribute_id or "").upper()

        if any(upper_id.startswith(prefix) for prefix in internal_prefixes):
            continue

        # Só envia atributos oficialmente retornados pela categoria.
        # BRAND, MODEL, GTIN e EMPTY_GTIN_REASON também precisam existir
        # no metadata cache para serem enviados.
        if upper_id not in official_ids:
            continue

        clean.append(payload)

    return clean


async def s212_attribute_validation(product_id, category_id):
    attrs = await s21_category_attrs(category_id)
    metadata = {
        str(attr.get("attribute_id") or "").upper(): attr
        for attr in attrs
        if attr.get("attribute_id")
    }
    values = await s21_product_values(product_id, category_id)

    gtin_row = values.get("GTIN") or values.get("gtin") or {}
    gtin_value = gtin_row.get("value_name") or gtin_row.get("value_id")
    gtin_valid = s212_valid_gtin(gtin_value)

    reason_row = values.get("EMPTY_GTIN_REASON") or values.get("empty_gtin_reason") or {}
    reason_value = reason_row.get("value_id") or reason_row.get("value_name")
    reason_payload = s212_value_payload(
        "EMPTY_GTIN_REASON",
        reason_row.get("value_id"),
        reason_row.get("value_name"),
        metadata.get("EMPTY_GTIN_REASON")
    )
    reason_valid = bool(reason_payload)

    # GTIN e EMPTY_GTIN_REASON são mutuamente exclusivos.
    if gtin_valid:
        reason_valid = False

    missing = []
    invalid = []
    filled = []

    for attr in attrs:
        aid = str(attr.get("attribute_id") or "").upper()
        required = bool(attr.get("required") or attr.get("catalog_required"))

        if aid == "GTIN":
            if gtin_value and not gtin_valid:
                invalid.append({
                    "attribute_id": "GTIN",
                    "name": attr.get("name"),
                    "message": "GTIN inválido. Use um código real de 8, 12, 13 ou 14 dígitos, ou deixe vazio e informe EMPTY_GTIN_REASON."
                })
            elif gtin_valid:
                filled.append({"attribute_id": "GTIN", "value_name": s212_digits(gtin_value)})
            elif required and "EMPTY_GTIN_REASON" not in metadata:
                missing.append({"attribute_id": "GTIN", "name": attr.get("name")})
            continue

        if aid == "EMPTY_GTIN_REASON":
            if gtin_valid:
                continue
            if reason_valid:
                filled.append({"attribute_id": aid, "value_name": reason_value})
            elif required or "EMPTY_GTIN_REASON" in metadata:
                missing.append({
                    "attribute_id": aid,
                    "name": attr.get("name"),
                    "message": "Informe o motivo permitido pelo Mercado Livre para o produto não possuir GTIN."
                })
            continue

        if not required:
            continue

        row = values.get(aid) or values.get(aid.lower()) or {}
        payload = s212_value_payload(
            aid,
            row.get("value_id"),
            row.get("value_name"),
            metadata.get(aid)
        )
        if payload:
            filled.append({
                "attribute_id": aid,
                "value_id": payload.get("value_id"),
                "value_name": payload.get("value_name")
            })
        else:
            missing.append({"attribute_id": aid, "name": attr.get("name")})

    return {
        "valid": not missing and not invalid,
        "gtin_valid": gtin_valid,
        "gtin": s212_digits(gtin_value) if gtin_valid else None,
        "empty_gtin_reason_valid": reason_valid if not gtin_valid else False,
        "required_count": len(filled) + len(missing),
        "filled_count": len(filled),
        "missing_count": len(missing),
        "invalid_count": len(invalid),
        "filled": filled,
        "missing": missing,
        "invalid": invalid,
    }


# ==========================================================
# SPRINT 22 - INTELLIGENT GTIN RESOLVER
# Consulta as opções permitidas pelo ML, salva value_id e resolve
# automaticamente o conflito GTIN x EMPTY_GTIN_REASON.
# ==========================================================

async def s22_gtin_metadata(category_id):
    attrs = await s21_category_attrs(category_id)
    metadata = {
        str(attr.get("attribute_id") or "").upper(): attr
        for attr in attrs
        if attr.get("attribute_id")
    }

    # Atualiza o cache caso o atributo ainda não esteja disponível.
    if "EMPTY_GTIN_REASON" not in metadata:
        await s21_sync_category(category_id)
        attrs = await s21_category_attrs(category_id)
        metadata = {
            str(attr.get("attribute_id") or "").upper(): attr
            for attr in attrs
            if attr.get("attribute_id")
        }

    return {
        "gtin": metadata.get("GTIN"),
        "empty_reason": metadata.get("EMPTY_GTIN_REASON"),
    }


def s22_allowed_reasons(metadata):
    metadata = metadata or {}
    options = []

    for item in metadata.get("values") or []:
        value_id = str(item.get("id") or "").strip()
        value_name = str(item.get("name") or value_id).strip()
        if value_id or value_name:
            options.append({
                "id": value_id or value_name,
                "name": value_name or value_id,
            })

    return options


async def s22_delete_attribute_value(product_id, attribute_id):
    # Apaga somente o valor específico deste produto/marketplace.
    return await store.delete(
        "product_marketplace_attributes",
        "product_id=eq."
        + quote(str(product_id), safe="-")
        + "&marketplace=eq.mercado_livre"
        + "&attribute_id=eq."
        + quote(str(attribute_id), safe="-_")
    )


async def s22_save_attribute_value(
    product_id,
    category_id,
    attribute_id,
    value_id=None,
    value_name=None,
    source="gtin_resolver",
):
    payload = {
        "company_id": DEFAULT_COMPANY_ID,
        "product_id": product_id,
        "marketplace": "mercado_livre",
        "category_id": category_id,
        "attribute_id": attribute_id,
        "value_id": value_id,
        "value_name": value_name,
        "source": source,
        "confidence": 100,
        "status": "active",
        "raw_data": {"resolver": "sprint22"},
    }
    return await store.upsert(
        "product_marketplace_attributes",
        payload,
        "product_id,marketplace,attribute_id"
    )


async def s22_resolve_gtin(product_id, category_id, mode, gtin=None, reason=None):
    mode = str(mode or "").strip().lower()
    metadata = await s22_gtin_metadata(category_id)
    reason_metadata = metadata.get("empty_reason") or {}
    allowed_reasons = s22_allowed_reasons(reason_metadata)

    if mode == "with_gtin":
        normalized = s212_digits(gtin)
        if not s212_valid_gtin(normalized):
            return {
                "success": False,
                "status_code": 422,
                "error": "GTIN inválido.",
                "message": "Informe um GTIN real com 8, 12, 13 ou 14 dígitos e dígito verificador válido.",
                "gtin": normalized,
            }

        saved = await s22_save_attribute_value(
            product_id,
            category_id,
            "GTIN",
            value_name=normalized,
            source="gtin_resolver",
        )
        if not saved.get("success"):
            return {
                "success": False,
                "status_code": 400,
                "error": saved.get("error") or saved.get("raw"),
            }

        await s22_delete_attribute_value(product_id, "EMPTY_GTIN_REASON")

        # Mantém o Product Master coerente com o valor escolhido.
        await store.update(
            "products",
            f"id=eq.{quote(str(product_id), safe='-')}",
            {"ean": normalized, "sync_status": "pending"},
        )

        return {
            "success": True,
            "mode": "with_gtin",
            "gtin": normalized,
            "removed": "EMPTY_GTIN_REASON",
        }

    if mode == "without_gtin":
        reason = str(reason or "").strip()
        if not reason:
            return {
                "success": False,
                "status_code": 422,
                "error": "Selecione um motivo para ausência de GTIN.",
                "allowed_reasons": allowed_reasons,
            }

        selected = None
        for option in allowed_reasons:
            if reason.lower() in {
                str(option.get("id") or "").lower(),
                str(option.get("name") or "").lower(),
            }:
                selected = option
                break

        if not selected:
            return {
                "success": False,
                "status_code": 422,
                "error": "Motivo não permitido para esta categoria.",
                "received": reason,
                "allowed_reasons": allowed_reasons,
            }

        saved = await s22_save_attribute_value(
            product_id,
            category_id,
            "EMPTY_GTIN_REASON",
            value_id=selected.get("id"),
            value_name=selected.get("name"),
            source="gtin_resolver",
        )
        if not saved.get("success"):
            return {
                "success": False,
                "status_code": 400,
                "error": saved.get("error") or saved.get("raw"),
            }

        await s22_delete_attribute_value(product_id, "GTIN")

        # Remove o EAN inválido do Product Master para impedir nova sugestão.
        await store.update(
            "products",
            f"id=eq.{quote(str(product_id), safe='-')}",
            {"ean": None, "sync_status": "pending"},
        )

        return {
            "success": True,
            "mode": "without_gtin",
            "empty_gtin_reason": selected,
            "removed": "GTIN",
        }

    return {
        "success": False,
        "status_code": 400,
        "error": "Modo inválido. Use with_gtin ou without_gtin.",
    }


@app.get("/api/gtin-resolver/category/{category_id}/options")
async def gtin_resolver_options(category_id: str):
    metadata = await s22_gtin_metadata(category_id)
    return {
        "success": True,
        "version": APP_VERSION,
        "category_id": category_id,
        "supports_gtin": bool(metadata.get("gtin")),
        "supports_empty_gtin_reason": bool(metadata.get("empty_reason")),
        "allowed_reasons": s22_allowed_reasons(metadata.get("empty_reason")),
        "metadata": metadata,
    }


@app.post("/api/gtin-resolver/product/{product_id}/category/{category_id}")
async def gtin_resolver_save(product_id: str, category_id: str, request: Request):
    form = await request.form()
    result = await s22_resolve_gtin(
        product_id=product_id,
        category_id=category_id,
        mode=form.get("mode"),
        gtin=form.get("gtin"),
        reason=form.get("reason"),
    )

    if not result.get("success"):
        return JSONResponse(
            status_code=int(result.get("status_code") or 400),
            content={
                "success": False,
                "version": APP_VERSION,
                **result,
            }
        )

    return RedirectResponse(
        f"/smart-category-engine/product/{product_id}/category/{category_id}",
        status_code=303
    )


@app.get("/api/gtin-resolver/product/{product_id}/category/{category_id}/status")
async def gtin_resolver_status(product_id: str, category_id: str):
    values = await s21_product_values(product_id, category_id)
    metadata = await s22_gtin_metadata(category_id)

    gtin = values.get("GTIN") or values.get("gtin") or {}
    reason = values.get("EMPTY_GTIN_REASON") or values.get("empty_gtin_reason") or {}

    return {
        "success": True,
        "version": APP_VERSION,
        "product_id": product_id,
        "category_id": category_id,
        "current": {
            "gtin": gtin,
            "empty_gtin_reason": reason,
        },
        "allowed_reasons": s22_allowed_reasons(metadata.get("empty_reason")),
        "validation": await s212_attribute_validation(product_id, category_id),
    }


# ==========================================================
# SPRINT 22.1 - GTIN RESOLVER UI
# Interface simples para escolher GTIN real ou motivo de ausência.
# ==========================================================

@app.get("/gtin-resolver/product/{product_id}/category/{category_id}", response_class=HTMLResponse)
async def gtin_resolver_page(product_id: str, category_id: str):
    metadata = await s22_gtin_metadata(category_id)
    allowed_reasons = s22_allowed_reasons(metadata.get("empty_reason"))
    values = await s21_product_values(product_id, category_id)

    gtin_row = values.get("GTIN") or values.get("gtin") or {}
    reason_row = values.get("EMPTY_GTIN_REASON") or values.get("empty_gtin_reason") or {}

    gtin_value = str(gtin_row.get("value_name") or "").strip()
    reason_value_id = str(reason_row.get("value_id") or "").strip()
    reason_value_name = str(reason_row.get("value_name") or "").strip()

    reason_options = "".join(
        f"<option value='{s19e(option.get('id'))}' "
        f"{'selected' if str(option.get('id') or '').lower() == reason_value_id.lower() else ''}>"
        f"{s19e(option.get('name'))}</option>"
        for option in allowed_reasons
    )

    selected_mode = "without_gtin" if (reason_value_id or reason_value_name) else "with_gtin"

    content = f"""
<div class='grid'>
  <div class='metric'><span>Produto</span><strong>{s19e(product_id[:8])}</strong></div>
  <div class='metric'><span>Categoria</span><strong>{s19e(category_id)}</strong></div>
  <div class='metric'><span>GTIN válido</span><strong>{'SIM' if s212_valid_gtin(gtin_value) else 'NÃO'}</strong></div>
  <div class='metric'><span>Motivo salvo</span><strong>{s19e(reason_value_name or '-')}</strong></div>
</div>

<div class='card'>
<h2>Resolvedor inteligente de GTIN</h2>
<p>Escolha uma opção. O CommerceHub removerá automaticamente o atributo conflitante.</p>

<form id='gtinResolverForm' method='post' action='/api/gtin-resolver/product/{product_id}/category/{category_id}'>
  <div style='display:flex;gap:20px;flex-wrap:wrap;margin-bottom:18px'>
    <label style='display:flex;align-items:center;gap:8px'>
      <input type='radio' name='mode' value='with_gtin' style='width:auto'
        {'checked' if selected_mode == 'with_gtin' else ''} onchange='toggleGtinMode()'>
      Produto possui GTIN
    </label>

    <label style='display:flex;align-items:center;gap:8px'>
      <input type='radio' name='mode' value='without_gtin' style='width:auto'
        {'checked' if selected_mode == 'without_gtin' else ''} onchange='toggleGtinMode()'>
      Produto não possui GTIN
    </label>
  </div>

  <div id='withGtinBox' style='border:1px solid #dbe3ef;border-radius:12px;padding:16px;margin-bottom:16px'>
    <label>GTIN real do produto</label>
    <input id='gtinInput' name='gtin' value='{s19e(gtin_value)}'
      placeholder='8, 12, 13 ou 14 dígitos'>
    <small>Use o código real da embalagem ou do fabricante.</small>
  </div>

  <div id='withoutGtinBox' style='border:1px solid #dbe3ef;border-radius:12px;padding:16px;margin-bottom:16px'>
    <label>Motivo permitido pelo Mercado Livre</label>
    <select id='reasonSelect' name='reason' style='width:100%;padding:10px'>
      <option value=''>Selecione...</option>
      {reason_options}
    </select>
    <small>As opções são carregadas dos metadados da categoria {s19e(category_id)}.</small>
  </div>

  <button type='submit'>Salvar decisão de GTIN</button>
  <a class='btn' href='/smart-category-engine/product/{product_id}/category/{category_id}'>Voltar aos atributos</a>
  <a class='btn' href='/api/gtin-resolver/product/{product_id}/category/{category_id}/status'>Ver status técnico</a>
</form>
</div>

<script>
function toggleGtinMode() {{
  const selected = document.querySelector('input[name="mode"]:checked');
  const withBox = document.getElementById('withGtinBox');
  const withoutBox = document.getElementById('withoutGtinBox');
  const gtinInput = document.getElementById('gtinInput');
  const reasonSelect = document.getElementById('reasonSelect');

  const mode = selected ? selected.value : 'with_gtin';

  if (mode === 'with_gtin') {{
    withBox.style.opacity = '1';
    withoutBox.style.opacity = '0.45';
    gtinInput.disabled = false;
    gtinInput.required = true;
    reasonSelect.disabled = true;
    reasonSelect.required = false;
  }} else {{
    withBox.style.opacity = '0.45';
    withoutBox.style.opacity = '1';
    gtinInput.disabled = true;
    gtinInput.required = false;
    reasonSelect.disabled = false;
    reasonSelect.required = true;
  }}
}}

document.addEventListener('DOMContentLoaded', toggleGtinMode);
</script>
"""
    return HTMLResponse(shell("Resolvedor de GTIN", content))


# ==========================================================
# SPRINT 23 - INTELLIGENT CATEGORY RULES
# Aprende com os metadados e com os erros reais do Mercado Livre.
# ==========================================================

def s23_text(value):
    return str(value or "").strip()


async def s23_category_rule_snapshot(category_id):
    attrs = await s21_category_attrs(category_id)
    by_id = {
        s23_text(attr.get("attribute_id")).upper(): attr
        for attr in attrs
        if attr.get("attribute_id")
    }

    gtin_meta = by_id.get("GTIN") or {}
    empty_meta = by_id.get("EMPTY_GTIN_REASON") or {}

    gtin_required = bool(
        gtin_meta.get("required")
        or gtin_meta.get("catalog_required")
        or (gtin_meta.get("tags") or {}).get("required")
        or (gtin_meta.get("tags") or {}).get("catalog_required")
    )

    empty_reason_supported = bool(empty_meta)
    empty_reason_values = s22_allowed_reasons(empty_meta)

    return {
        "category_id": category_id,
        "gtin_required": gtin_required,
        "empty_gtin_reason_supported": empty_reason_supported,
        "empty_gtin_reason_values": empty_reason_values,
        "attributes_cached": len(attrs),
        "source": "mercado_livre_category_metadata",
    }


async def s23_product_category_rule(product_id, category_id):
    values = await s21_product_values(product_id, category_id)
    snapshot = await s23_category_rule_snapshot(category_id)

    gtin_row = values.get("GTIN") or values.get("gtin") or {}
    reason_row = (
        values.get("EMPTY_GTIN_REASON")
        or values.get("empty_gtin_reason")
        or {}
    )

    gtin_value = gtin_row.get("value_name") or gtin_row.get("value_id")
    has_valid_gtin = s212_valid_gtin(gtin_value)
    has_empty_reason = bool(
        reason_row.get("value_id") or reason_row.get("value_name")
    )

    if has_valid_gtin:
        mode = "gtin"
        allowed = True
        blocking_reason = None
    elif has_empty_reason and snapshot.get("empty_gtin_reason_supported") and not snapshot.get("gtin_required"):
        mode = "empty_gtin_reason"
        allowed = True
        blocking_reason = None
    elif has_empty_reason and snapshot.get("gtin_required"):
        mode = "blocked_category_requires_gtin"
        allowed = False
        blocking_reason = "Esta categoria exige GTIN válido e não aceita somente EMPTY_GTIN_REASON."
    elif not has_valid_gtin and not has_empty_reason:
        mode = "missing_gtin_decision"
        allowed = False
        blocking_reason = "Informe um GTIN válido ou selecione um motivo de ausência permitido."
    else:
        mode = "blocked"
        allowed = False
        blocking_reason = "A regra de GTIN desta categoria não foi atendida."

    return {
        "success": True,
        "product_id": product_id,
        "category_id": category_id,
        "allowed_to_publish": allowed,
        "mode": mode,
        "blocking_reason": blocking_reason,
        "has_valid_gtin": has_valid_gtin,
        "has_empty_gtin_reason": has_empty_reason,
        "category_rules": snapshot,
        "current_values": {
            "gtin": gtin_row,
            "empty_gtin_reason": reason_row,
        },
    }


async def s23_record_ml_rule_feedback(product_id, category_id, result):
    error_text = s202_ml_error_text(result)
    detected_rule = None

    if "attributes [gtin] are required" in error_text or "missing_conditional_required" in error_text:
        detected_rule = "gtin_required_even_with_empty_reason"

    if not detected_rule:
        return {"success": True, "recorded": False}

    payload = {
        "company_id": DEFAULT_COMPANY_ID,
        "product_id": product_id,
        "marketplace": "mercado_livre",
        "category_id": category_id,
        "attribute_id": "CATEGORY_RULE_GTIN_REQUIRED",
        "value_name": "true",
        "source": "mercado_livre_error_feedback",
        "confidence": 100,
        "status": "active",
        "raw_data": {
            "rule": detected_rule,
            "error": result.get("data") or result.get("raw") or result.get("error"),
        },
    }

    saved = await store.upsert(
        "product_marketplace_attributes",
        payload,
        "product_id,marketplace,attribute_id"
    )

    return {
        "success": bool(saved.get("success")),
        "recorded": bool(saved.get("success")),
        "rule": detected_rule,
        "result": saved,
    }


async def s23_product_feedback_rule(product_id, category_id=None):
    query = (
        "select=*&product_id=eq."
        + quote(str(product_id), safe="-")
        + "&marketplace=eq.mercado_livre"
        + "&attribute_id=eq.CATEGORY_RULE_GTIN_REQUIRED"
    )
    if category_id:
        query += "&category_id=eq." + quote(str(category_id), safe="-_")

    result = await store.select("product_marketplace_attributes", query + "&limit=1")
    rows = result.get("data") or []
    row = rows[0] if rows else {}

    return bool(
        s23_text(row.get("value_name")).lower() == "true"
        or s23_text(row.get("value_id")).lower() == "true"
    )


@app.get("/api/category-rules/category/{category_id}")
async def category_rules_category(category_id: str):
    snapshot = await s23_category_rule_snapshot(category_id)
    return {
        "success": True,
        "version": APP_VERSION,
        **snapshot,
    }


@app.get("/api/category-rules/product/{product_id}/category/{category_id}")
async def category_rules_product(product_id: str, category_id: str):
    rule = await s23_product_category_rule(product_id, category_id)
    feedback_rule = await s23_product_feedback_rule(product_id, category_id)

    if feedback_rule and rule.get("mode") == "empty_gtin_reason":
        rule["allowed_to_publish"] = False
        rule["mode"] = "blocked_by_ml_feedback"
        rule["blocking_reason"] = (
            "O Mercado Livre já confirmou que esta categoria exige GTIN válido "
            "para este fluxo de publicação."
        )

    rule["feedback_gtin_required"] = feedback_rule
    rule["version"] = APP_VERSION
    return rule


@app.get("/category-rules/product/{product_id}/category/{category_id}", response_class=HTMLResponse)
async def category_rules_page(product_id: str, category_id: str):
    rule = await category_rules_product(product_id, category_id)

    status = "LIBERADO" if rule.get("allowed_to_publish") else "BLOQUEADO"
    reason = rule.get("blocking_reason") or "Nenhum bloqueio identificado."
    category_rules = rule.get("category_rules") or {}
    reasons = category_rules.get("empty_gtin_reason_values") or []

    reasons_html = "".join(
        f"<li>{s19e(item.get('name'))} <small>({s19e(item.get('id'))})</small></li>"
        for item in reasons
    ) or "<li>Nenhuma opção de ausência de GTIN disponível.</li>"

    content = f"""
<div class='grid'>
  <div class='metric'><span>Status</span><strong>{status}</strong></div>
  <div class='metric'><span>Categoria</span><strong>{s19e(category_id)}</strong></div>
  <div class='metric'><span>GTIN obrigatório</span><strong>{'SIM' if category_rules.get('gtin_required') else 'NÃO'}</strong></div>
  <div class='metric'><span>Motivo sem GTIN</span><strong>{'ACEITO' if category_rules.get('empty_gtin_reason_supported') else 'NÃO SUPORTADO'}</strong></div>
</div>

<div class='card'>
<h2>Regra inteligente da categoria</h2>
<p><b>Resultado:</b> {status}</p>
<p><b>Modo identificado:</b> {s19e(rule.get('mode'))}</p>
<p><b>Motivo:</b> {s19e(reason)}</p>
</div>

<div class='card'>
<h2>Motivos de ausência de GTIN disponíveis</h2>
<ul>{reasons_html}</ul>
</div>

<div class='card'>
<a class='btn' href='/gtin-resolver/product/{product_id}/category/{category_id}'>Resolver GTIN</a>
<a class='btn' href='/smart-category-engine/product/{product_id}/category/{category_id}'>Atributos inteligentes</a>
<a class='btn' href='/product-master/{product_id}/listing'>Voltar ao anúncio</a>
</div>
"""
    return HTMLResponse(shell("Regras da Categoria", content))


# ==========================================================
# SPRINT 24 - MARKETPLACE METADATA PREFLIGHT
# Consulta metadados oficiais e regras condicionais antes do POST /items.
# ==========================================================

def s24_extract_attribute_ids(value):
    found = set()

    def walk(node):
        if isinstance(node, dict):
            candidate = node.get("id") or node.get("attribute_id")
            if candidate:
                found.add(str(candidate).upper())

            for key, item in node.items():
                key_lower = str(key).lower()
                if key_lower in {
                    "required_attributes",
                    "conditional_attributes",
                    "missing_attributes",
                    "attributes",
                    "causes",
                    "references",
                }:
                    walk(item)
                elif isinstance(item, (dict, list)):
                    walk(item)

        elif isinstance(node, list):
            for item in node:
                walk(item)

        elif isinstance(node, str):
            text = node.upper()
            for token in re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", text):
                if token not in {
                    "POST", "GET", "HTTP", "JSON", "ERROR", "TRUE", "FALSE",
                    "BRL", "MLB", "ITEM", "ITEMS", "VALIDATION"
                }:
                    found.add(token)

    walk(value)
    return sorted(found)


async def s24_conditional_metadata(category_id, payload):
    path = f"/categories/{quote(str(category_id), safe='-_')}/attributes/conditional"

    # A documentação oficial descreve esta validação com o payload do produto.
    first = await ml_request(path, method="POST", payload=payload)

    # Algumas versões da API podem esperar apenas attributes.
    if not first.get("success") and first.get("status_code") in (400, 404, 405):
        second = await ml_request(
            path,
            method="POST",
            payload={"attributes": payload.get("attributes") or []}
        )
        if second.get("success"):
            return {
                "success": True,
                "request_shape": "attributes_only",
                "result": second,
            }

    return {
        "success": bool(first.get("success")),
        "request_shape": "full_item",
        "result": first,
    }


async def s24_metadata_preflight(context, listing):
    product_id = context["product"].get("id")
    category_id = listing.get("category_id")

    await s21_sync_category(category_id)
    metadata = await s212_attribute_metadata(category_id)
    category_rule = await s23_product_category_rule(product_id, category_id)
    learned_gtin_rule = await s23_product_feedback_rule(product_id, category_id)

    payload = s19_build_ml_payload(context, listing, mode="user_product")
    payload["attributes"] = await s21_payload_attributes(
        product_id,
        category_id,
        payload.get("attributes")
    )

    official_ids = sorted(metadata.keys())
    sent_ids = sorted(
        str(item.get("id") or "").upper()
        for item in payload.get("attributes") or []
        if item.get("id")
    )
    filtered_ids = sorted(set(sent_ids) - set(official_ids))

    conditional = await s24_conditional_metadata(category_id, payload)
    conditional_result = conditional.get("result") or {}
    conditional_ids = s24_extract_attribute_ids(
        conditional_result.get("data")
        or conditional_result.get("raw")
        or conditional_result.get("error")
    )

    blockers = []
    warnings = []

    intelligence = await s25_intelligence_assessment(context, listing)
    for item in intelligence.get("blockers") or []:
        blockers.append({
            "code": item.get("code"),
            "message": item.get("message"),
            "rule": item.get("rule"),
        })

    if filtered_ids:
        blockers.append({
            "code": "non_official_attributes",
            "message": "O payload contém atributos que não existem nos metadados da categoria.",
            "attributes": filtered_ids,
        })

    if learned_gtin_rule and not category_rule.get("has_valid_gtin"):
        blockers.append({
            "code": "learned_gtin_required",
            "message": "O Mercado Livre já confirmou que esta categoria exige GTIN válido.",
            "attribute": "GTIN",
        })

    if not category_rule.get("allowed_to_publish"):
        blockers.append({
            "code": "category_rule_blocked",
            "message": category_rule.get("blocking_reason"),
        })

    if conditional.get("success"):
        missing_conditionals = [
            attr_id
            for attr_id in conditional_ids
            if attr_id in official_ids and attr_id not in sent_ids
        ]
        if missing_conditionals:
            blockers.append({
                "code": "conditional_required_missing",
                "message": "A validação condicional retornou atributos ainda não enviados.",
                "attributes": missing_conditionals,
            })
    else:
        warnings.append({
            "code": "conditional_endpoint_unavailable",
            "message": "A API condicional não respondeu com sucesso; as demais validações continuam ativas.",
            "status_code": conditional_result.get("status_code"),
            "error": str(
                conditional_result.get("error")
                or conditional_result.get("raw")
                or ""
            )[:800],
        })

    return {
        "success": len(blockers) == 0,
        "version": APP_VERSION,
        "product_id": product_id,
        "category_id": category_id,
        "payload_preview": payload,
        "official_attribute_ids": official_ids,
        "sent_attribute_ids": sent_ids,
        "conditional_attribute_ids": conditional_ids,
        "category_rule": category_rule,
        "learned_gtin_required": learned_gtin_rule,
        "conditional_validation": conditional,
        "blockers": blockers,
        "warnings": warnings,
        "intelligence": intelligence,
    }


@app.get("/api/metadata-preflight/listing/{listing_id}")
async def metadata_preflight_endpoint(listing_id: str):
    listing = await s19_get_listing(listing_id)
    if not listing:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Anúncio não encontrado."}
        )

    context = await s19_product_context(listing.get("product_id"))
    if not context:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Produto não encontrado."}
        )

    return await s24_metadata_preflight(context, listing)


@app.get("/metadata-preflight/listing/{listing_id}", response_class=HTMLResponse)
async def metadata_preflight_page(listing_id: str):
    listing = await s19_get_listing(listing_id)
    if not listing:
        return HTMLResponse(shell("Metadata Preflight", "<div class='card'>Anúncio não encontrado.</div>"), status_code=404)

    context = await s19_product_context(listing.get("product_id"))
    result = await s24_metadata_preflight(context, listing)

    blockers = result.get("blockers") or []
    warnings = result.get("warnings") or []

    blockers_html = "".join(
        f"<li><b>{s19e(item.get('code'))}</b>: {s19e(item.get('message'))} "
        f"{s19e(', '.join(item.get('attributes') or []))}</li>"
        for item in blockers
    ) or "<li>Nenhum bloqueio encontrado.</li>"

    warnings_html = "".join(
        f"<li><b>{s19e(item.get('code'))}</b>: {s19e(item.get('message'))}</li>"
        for item in warnings
    ) or "<li>Nenhum alerta.</li>"

    category_rule = result.get("category_rule") or {}

    content = f"""
<div class='grid'>
  <div class='metric'><span>Status</span><strong>{'LIBERADO' if result.get('success') else 'BLOQUEADO'}</strong></div>
  <div class='metric'><span>Categoria</span><strong>{s19e(result.get('category_id'))}</strong></div>
  <div class='metric'><span>Atributos oficiais</span><strong>{len(result.get('official_attribute_ids') or [])}</strong></div>
  <div class='metric'><span>Atributos enviados</span><strong>{len(result.get('sent_attribute_ids') or [])}</strong></div>
</div>

<div class='card'>
<h2>Bloqueios</h2>
<ul>{blockers_html}</ul>
<h2>Alertas</h2>
<ul>{warnings_html}</ul>
</div>

<div class='card'>
<h2>Regra de GTIN</h2>
<p><b>GTIN válido:</b> {'SIM' if category_rule.get('has_valid_gtin') else 'NÃO'}</p>
<p><b>Motivo sem GTIN:</b> {'SIM' if category_rule.get('has_empty_gtin_reason') else 'NÃO'}</p>
<p><b>Regra aprendida:</b> {'GTIN obrigatório' if result.get('learned_gtin_required') else 'Nenhuma'}</p>
<p><b>Modo:</b> {s19e(category_rule.get('mode'))}</p>
</div>

<div class='card'>
<h2>Atributos do payload</h2>
<p>{s19e(', '.join(result.get('sent_attribute_ids') or []))}</p>
<h2>Atributos condicionais detectados</h2>
<p>{s19e(', '.join(result.get('conditional_attribute_ids') or []))}</p>
</div>

<div class='card'>
<a class='btn' href='/product-master/{listing.get("product_id")}/listing'>Voltar ao anúncio</a>
<a class='btn' href='/gtin-resolver/product/{listing.get("product_id")}/category/{listing.get("category_id")}'>Resolver GTIN</a>
<a class='btn' href='/api/metadata-preflight/listing/{listing_id}'>Ver JSON técnico</a>
</div>
"""
    return HTMLResponse(shell("Marketplace Metadata Preflight", content))


# ==========================================================
# SPRINT 25 - MARKETPLACE INTELLIGENCE ENGINE
# Aprende regras por categoria, marca e erro real do marketplace.
# ==========================================================

def s25_json_safe(value):
    try:
        json.dumps(value, ensure_ascii=False, default=str)
        return value
    except Exception:
        return {"raw": str(value)}


def s25_ml_causes(result):
    data = result.get("data") if isinstance(result, dict) else {}
    causes = data.get("cause") if isinstance(data, dict) else None
    if isinstance(causes, list):
        return causes
    return []


async def s25_upsert_rule(
    category_id,
    rule_key,
    rule_value,
    brand=None,
    domain_id=None,
    source="api_feedback",
    confidence=100,
    error_code=None,
    error_message=None,
):
    query = (
        "select=*&marketplace=eq.mercado_livre"
        + "&category_id=eq." + quote(str(category_id), safe="-_")
        + "&rule_key=eq." + quote(str(rule_key), safe="-_")
        + "&limit=1"
    )

    if brand:
        query += "&brand=eq." + quote(str(brand), safe="-_ ")
    else:
        query += "&brand=is.null"

    if domain_id:
        query += "&domain_id=eq." + quote(str(domain_id), safe="-_")
    else:
        query += "&domain_id=is.null"

    existing_result = await store.select("marketplace_rule_knowledge", query)
    existing_rows = existing_result.get("data") or []
    existing = existing_rows[0] if existing_rows else None

    now_value = __import__("datetime").datetime.utcnow().isoformat()

    if existing:
        update_payload = {
            "rule_value": s25_json_safe(rule_value),
            "source": source,
            "confidence": confidence,
            "hit_count": int(existing.get("hit_count") or 0) + 1,
            "last_error_code": error_code,
            "last_error_message": error_message,
            "last_seen_at": now_value,
            "active": True,
        }
        return await store.update(
            "marketplace_rule_knowledge",
            "id=eq." + quote(str(existing.get("id")), safe="-"),
            update_payload,
        )

    insert_payload = {
        "company_id": DEFAULT_COMPANY_ID,
        "marketplace": "mercado_livre",
        "category_id": category_id,
        "domain_id": domain_id,
        "brand": brand,
        "rule_key": rule_key,
        "rule_value": s25_json_safe(rule_value),
        "source": source,
        "confidence": confidence,
        "hit_count": 1,
        "last_error_code": error_code,
        "last_error_message": error_message,
        "active": True,
        "first_seen_at": now_value,
        "last_seen_at": now_value,
    }
    return await store.insert("marketplace_rule_knowledge", insert_payload)


async def s25_get_rules(category_id, brand=None):
    query = (
        "select=*&marketplace=eq.mercado_livre"
        + "&category_id=eq." + quote(str(category_id), safe="-_")
        + "&active=eq.true"
        + "&order=confidence.desc,last_seen_at.desc"
    )
    result = await store.select("marketplace_rule_knowledge", query)
    rows = result.get("data") or []

    filtered = []
    for row in rows:
        row_brand = str(row.get("brand") or "").strip()
        if row_brand and brand and row_brand.lower() != str(brand).strip().lower():
            continue
        if row_brand and not brand:
            continue
        filtered.append(row)

    return filtered


async def s25_record_error(
    context,
    listing,
    result,
    payload,
):
    product = context.get("product") or {}
    causes = s25_ml_causes(result)

    if not causes:
        causes = [{
            "code": (result.get("data") or {}).get("message") if isinstance(result.get("data"), dict) else None,
            "cause_id": None,
            "department": None,
            "message": result.get("error") or result.get("raw"),
        }]

    saved = 0
    learned = []

    for cause in causes:
        code_value = str(cause.get("code") or "").strip()
        cause_id = str(cause.get("cause_id") or "").strip()
        message = str(cause.get("message") or "").strip()
        department = str(cause.get("department") or "").strip()

        row = {
            "company_id": DEFAULT_COMPANY_ID,
            "marketplace": "mercado_livre",
            "product_id": product.get("id"),
            "listing_id": listing.get("id"),
            "category_id": listing.get("category_id"),
            "brand": product.get("brand"),
            "error_code": code_value or None,
            "cause_id": cause_id or None,
            "department": department or None,
            "message": message or None,
            "payload_snapshot": s25_json_safe(payload or {}),
            "response_snapshot": s25_json_safe(result or {}),
            "resolution_key": None,
            "resolved": False,
        }
        insert_result = await store.insert("marketplace_error_knowledge", row)
        if insert_result.get("success"):
            saved += 1

        text = f"{code_value} {message}".lower()

        if (
            "missing_conditional_required" in text
            and "gtin" in text
        ):
            rule = await s25_upsert_rule(
                listing.get("category_id"),
                "GTIN_REQUIRED",
                {
                    "required": True,
                    "empty_gtin_reason_substitutes": False,
                    "evidence": "conditional_required",
                },
                brand=product.get("brand"),
                source="mercado_livre_error",
                confidence=100,
                error_code=code_value,
                error_message=message,
            )
            learned.append({
                "rule_key": "GTIN_REQUIRED",
                "success": bool(rule.get("success")),
            })

        if "product_identifier.invalid_format" in text and "gtin" in text:
            rule = await s25_upsert_rule(
                listing.get("category_id"),
                "GTIN_FORMAT_VALIDATION",
                {
                    "validate_structure": True,
                    "requires_real_product_identifier": True,
                },
                brand=product.get("brand"),
                source="mercado_livre_error",
                confidence=100,
                error_code=code_value,
                error_message=message,
            )
            learned.append({
                "rule_key": "GTIN_FORMAT_VALIDATION",
                "success": bool(rule.get("success")),
            })

        if "body.invalid_fields" in text and "title" in text:
            rule = await s25_upsert_rule(
                listing.get("category_id"),
                "USER_PRODUCT_FAMILY_NAME_FLOW",
                {
                    "use_family_name": True,
                    "send_title": False,
                },
                brand=product.get("brand"),
                source="mercado_livre_error",
                confidence=95,
                error_code=code_value,
                error_message=message,
            )
            learned.append({
                "rule_key": "USER_PRODUCT_FAMILY_NAME_FLOW",
                "success": bool(rule.get("success")),
            })

    return {
        "success": True,
        "errors_saved": saved,
        "rules_learned": learned,
    }


async def s25_intelligence_assessment(context, listing):
    product = context.get("product") or {}
    category_id = listing.get("category_id")
    brand = product.get("brand")

    rules = await s25_get_rules(category_id, brand)
    by_key = {
        str(row.get("rule_key") or "").upper(): row
        for row in rules
    }

    values = await s21_product_values(product.get("id"), category_id)
    gtin_row = values.get("GTIN") or values.get("gtin") or {}
    reason_row = values.get("EMPTY_GTIN_REASON") or values.get("empty_gtin_reason") or {}

    gtin_value = gtin_row.get("value_name") or gtin_row.get("value_id")
    has_valid_gtin = s212_valid_gtin(gtin_value)
    has_reason = bool(reason_row.get("value_id") or reason_row.get("value_name"))

    blockers = []
    recommendations = []

    gtin_rule = by_key.get("GTIN_REQUIRED")
    if gtin_rule and not has_valid_gtin:
        blockers.append({
            "code": "learned_gtin_required",
            "message": (
                "A base de inteligência confirmou que esta categoria/marca "
                "exige GTIN válido."
            ),
            "rule": gtin_rule.get("rule_value"),
        })
        recommendations.append({
            "action": "provide_real_gtin",
            "message": "Informe o GTIN real da embalagem ou do fabricante.",
        })

    if has_reason and gtin_rule:
        recommendations.append({
            "action": "do_not_use_empty_gtin_reason",
            "message": (
                "EMPTY_GTIN_REASON já foi recusado para esta combinação "
                "de categoria e marca."
            ),
        })

    return {
        "success": len(blockers) == 0,
        "category_id": category_id,
        "brand": brand,
        "rules_count": len(rules),
        "rules": rules,
        "blockers": blockers,
        "recommendations": recommendations,
        "current": {
            "has_valid_gtin": has_valid_gtin,
            "has_empty_gtin_reason": has_reason,
        },
    }


@app.get("/api/marketplace-intelligence/category/{category_id}")
async def marketplace_intelligence_category(category_id: str, brand: str = ""):
    rules = await s25_get_rules(category_id, brand or None)
    return {
        "success": True,
        "version": APP_VERSION,
        "category_id": category_id,
        "brand": brand or None,
        "rules_count": len(rules),
        "rules": rules,
    }


@app.get("/api/marketplace-intelligence/listing/{listing_id}")
async def marketplace_intelligence_listing(listing_id: str):
    listing = await s19_get_listing(listing_id)
    if not listing:
        return JSONResponse(status_code=404, content={
            "success": False,
            "error": "Anúncio não encontrado.",
        })

    context = await s19_product_context(listing.get("product_id"))
    if not context:
        return JSONResponse(status_code=404, content={
            "success": False,
            "error": "Produto não encontrado.",
        })

    try:
        preflight_result = await s24_metadata_preflight(context, listing)
        learning = await s251_learn_from_preflight(context, listing, preflight_result)
    except Exception as exc:
        learning = {"success": False, "learned": [], "error": str(exc)}

    return {
        "success": True,
        "version": APP_VERSION,
        "learning": learning,
        "assessment": await s25_intelligence_assessment(context, listing),
    }


@app.get("/marketplace-intelligence/listing/{listing_id}", response_class=HTMLResponse)
async def marketplace_intelligence_page(listing_id: str):
    listing = await s19_get_listing(listing_id)
    if not listing:
        return HTMLResponse(
            shell("Marketplace Intelligence", "<div class='card'>Anúncio não encontrado.</div>"),
            status_code=404,
        )

    context = await s19_product_context(listing.get("product_id"))
    try:
        preflight_result = await s24_metadata_preflight(context, listing)
        await s251_learn_from_preflight(context, listing, preflight_result)
    except Exception:
        pass
    assessment = await s25_intelligence_assessment(context, listing)

    blockers = assessment.get("blockers") or []
    recommendations = assessment.get("recommendations") or []
    rules = assessment.get("rules") or []

    blockers_html = "".join(
        f"<li><b>{s19e(item.get('code'))}</b>: {s19e(item.get('message'))}</li>"
        for item in blockers
    ) or "<li>Nenhum bloqueio aprendido.</li>"

    recommendations_html = "".join(
        f"<li><b>{s19e(item.get('action'))}</b>: {s19e(item.get('message'))}</li>"
        for item in recommendations
    ) or "<li>Nenhuma recomendação adicional.</li>"

    rows = "".join(
        f"""<tr>
<td>{s19e(row.get('rule_key'))}</td>
<td>{s19e(row.get('brand') or 'Todas')}</td>
<td>{s19e(row.get('source'))}</td>
<td>{s19e(row.get('confidence'))}</td>
<td>{s19e(row.get('hit_count'))}</td>
<td>{s19e(row.get('last_error_code') or '-')}</td>
</tr>"""
        for row in rules
    ) or "<tr><td colspan='6'>Nenhuma regra aprendida.</td></tr>"

    content = f"""
<div class='grid'>
  <div class='metric'><span>Status</span><strong>{'LIBERADO' if assessment.get('success') else 'BLOQUEADO'}</strong></div>
  <div class='metric'><span>Categoria</span><strong>{s19e(assessment.get('category_id'))}</strong></div>
  <div class='metric'><span>Marca</span><strong>{s19e(assessment.get('brand') or '-')}</strong></div>
  <div class='metric'><span>Regras aprendidas</span><strong>{assessment.get('rules_count')}</strong></div>
</div>

<div class='card'>
<h2>Bloqueios aprendidos</h2>
<ul>{blockers_html}</ul>
<h2>Recomendações</h2>
<ul>{recommendations_html}</ul>
</div>

<div class='card'>
<h2>Base de conhecimento aplicada</h2>
<table>
<thead><tr><th>Regra</th><th>Marca</th><th>Fonte</th><th>Confiança</th><th>Ocorrências</th><th>Último erro</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>

<div class='card'>
<a class='btn' href='/marketplace-intelligence/listing/{listing_id}/refresh'>Atualizar inteligência</a>
<a class='btn' href='/metadata-preflight/listing/{listing_id}'>Metadata Preflight</a>
<a class='btn' href='/product-master/{listing.get("product_id")}/listing'>Voltar ao anúncio</a>
<a class='btn' href='/api/marketplace-intelligence/listing/{listing_id}'>Ver JSON técnico</a>
</div>
"""
    return HTMLResponse(shell("Marketplace Intelligence Engine", content))


# ==========================================================
# SPRINT 25.1 - AUTO LEARNING PREFLIGHT
# Aprende com o endpoint condicional antes do POST /items.
# ==========================================================

async def s251_learn_from_preflight(context, listing, preflight_result):
    product = context.get("product") or {}
    category_id = listing.get("category_id")
    brand = product.get("brand")

    conditional_ids = {
        str(item or "").upper()
        for item in (preflight_result.get("conditional_attribute_ids") or [])
    }
    sent_ids = {
        str(item or "").upper()
        for item in (preflight_result.get("sent_attribute_ids") or [])
    }

    values = await s21_product_values(product.get("id"), category_id)
    reason_row = (
        values.get("EMPTY_GTIN_REASON")
        or values.get("empty_gtin_reason")
        or {}
    )
    has_empty_reason = bool(
        reason_row.get("value_id") or reason_row.get("value_name")
    )

    learned = []

    if "GTIN" in conditional_ids and "GTIN" not in sent_ids and has_empty_reason:
        saved = await s25_upsert_rule(
            category_id=category_id,
            rule_key="GTIN_REQUIRED",
            rule_value={
                "required": True,
                "empty_gtin_reason_substitutes": False,
                "evidence": "conditional_metadata",
                "conditional_attribute": "GTIN",
            },
            brand=brand,
            source="mercado_livre_conditional_metadata",
            confidence=100,
            error_code="conditional_required",
            error_message=(
                "O endpoint condicional exigiu GTIN mesmo com "
                "EMPTY_GTIN_REASON presente."
            ),
        )
        learned.append({
            "rule_key": "GTIN_REQUIRED",
            "success": bool(saved.get("success")),
            "source": "conditional_metadata",
        })

    legacy_rule = await s23_product_feedback_rule(product.get("id"), category_id)
    if legacy_rule:
        saved = await s25_upsert_rule(
            category_id=category_id,
            rule_key="GTIN_REQUIRED",
            rule_value={
                "required": True,
                "empty_gtin_reason_substitutes": False,
                "evidence": "legacy_ml_feedback",
            },
            brand=brand,
            source="legacy_marketplace_feedback",
            confidence=100,
            error_code="7810",
            error_message="Regra migrada do aprendizado anterior do CommerceHub.",
        )
        learned.append({
            "rule_key": "GTIN_REQUIRED",
            "success": bool(saved.get("success")),
            "source": "legacy_feedback",
        })

    return {
        "success": True,
        "learned": learned,
        "learned_count": len(learned),
    }


async def s251_refresh_listing_intelligence(listing_id):
    listing = await s19_get_listing(listing_id)
    if not listing:
        return {"success": False, "status_code": 404, "error": "Anúncio não encontrado."}

    context = await s19_product_context(listing.get("product_id"))
    if not context:
        return {"success": False, "status_code": 404, "error": "Produto não encontrado."}

    preflight = await s24_metadata_preflight(context, listing)
    learning = await s251_learn_from_preflight(context, listing, preflight)
    assessment = await s25_intelligence_assessment(context, listing)

    return {
        "success": True,
        "version": APP_VERSION,
        "listing_id": listing_id,
        "learning": learning,
        "assessment": assessment,
        "preflight": preflight,
    }


@app.get("/api/marketplace-intelligence/listing/{listing_id}/refresh")
async def marketplace_intelligence_refresh(listing_id: str):
    result = await s251_refresh_listing_intelligence(listing_id)
    if not result.get("success"):
        return JSONResponse(
            status_code=int(result.get("status_code") or 400),
            content=result,
        )
    return result


@app.get("/marketplace-intelligence/listing/{listing_id}/refresh")
async def marketplace_intelligence_refresh_page(listing_id: str):
    result = await s251_refresh_listing_intelligence(listing_id)
    if not result.get("success"):
        return JSONResponse(
            status_code=int(result.get("status_code") or 400),
            content=result,
        )
    return RedirectResponse(
        f"/marketplace-intelligence/listing/{listing_id}",
        status_code=303,
    )


# ==========================================================
# SPRINT 26 - PUBLISHING LAB
# Descoberta, comparação, simulação e publicação controlada.
# ==========================================================

def s26_location(attr):
    tags = s272_dict(attr.get("tags"))
    return "variation" if (
        attr.get("allow_variations")
        or tags.get("allow_variations")
        or tags.get("variation_attribute")
        or tags.get("defines_picture")
    ) else "item"


async def s26_discover(category_id):
    await s21_sync_category(category_id)
    attrs = await s21_category_attrs(category_id)
    item, variation, required = [], [], []
    for attr in attrs:
        row = {
            "attribute_id": attr.get("attribute_id"),
            "name": attr.get("name"),
            "required": bool(attr.get("required") or attr.get("catalog_required")),
            "value_type": attr.get("value_type"),
            "location": s26_location(attr),
        }
        (variation if row["location"] == "variation" else item).append(row)
        if row["required"]:
            required.append(row)
    return {
        "category_id": category_id,
        "attributes_count": len(attrs),
        "item_attributes": item,
        "variation_attributes": variation,
        "required_attributes": required,
        "official_ids": [str(a.get("attribute_id") or "").upper() for a in attrs],
    }


async def s26_payload(context, listing):
    payload = s19_build_ml_payload(context, listing, mode="user_product")
    payload["attributes"] = await s21_payload_attributes(
        context["product"].get("id"),
        listing.get("category_id"),
        payload.get("attributes")
    )
    discovery = await s26_discover(listing.get("category_id"))
    variation_ids = {str(x.get("attribute_id") or "").upper() for x in discovery["variation_attributes"]}
    item_attrs, variation_attrs = [], []
    for attr in payload.get("attributes") or []:
        (variation_attrs if str(attr.get("id") or "").upper() in variation_ids else item_attrs).append(attr)
    payload["attributes"] = item_attrs
    if variation_attrs:
        payload["variations"] = [{
            "price": payload.get("price"),
            "available_quantity": payload.get("available_quantity"),
            "attribute_combinations": variation_attrs,
            "picture_ids": [],
        }]
    return payload, discovery, variation_attrs


async def s26_simulate(context, listing):
    payload, discovery, variation_attrs = await s26_payload(context, listing)
    preflight = await s24_metadata_preflight(context, listing)
    intelligence = await s25_intelligence_assessment(context, listing)
    sent = {str(x.get("id") or "").upper() for x in payload.get("attributes") or []}
    official = set(discovery.get("official_ids") or [])
    conditional = set(preflight.get("conditional_attribute_ids") or [])
    blockers = list(preflight.get("blockers") or [])
    warnings = list(preflight.get("warnings") or [])
    unknown = sorted(sent - official)
    missing = sorted(conditional - sent)
    for aid in unknown:
        blockers.append({"code":"unknown_attribute","message":f"Atributo {aid} não existe na categoria.","attribute":aid})
    for aid in missing:
        blockers.append({"code":"conditional_required_missing","message":f"Atributo condicional {aid} está faltando.","attribute":aid})
    if variation_attrs:
        warnings.append({"code":"variation_payload_generated","message":"Atributos de variação foram movidos para attribute_combinations.","attributes":[x.get("id") for x in variation_attrs]})
    score=max(0,100-min(80,len(blockers)*20)-min(20,len(warnings)*5))
    return {
        "success": not blockers,
        "status": "ready" if not blockers else "blocked",
        "score": score,
        "payload": payload,
        "discovery": discovery,
        "preflight": preflight,
        "intelligence": intelligence,
        "blockers": blockers,
        "warnings": warnings,
        "recommendations": intelligence.get("recommendations") or [],
        "comparison": {
            "sent_attribute_ids": sorted(sent),
            "unknown_attribute_ids": unknown,
            "missing_conditional_ids": missing,
        },
    }


async def s26_store_run(listing, result):
    run_id=str(uuid.uuid4())
    saved=await store.insert("publishing_lab_runs", {
        "id": run_id,
        "company_id": DEFAULT_COMPANY_ID,
        "marketplace": "mercado_livre",
        "product_id": listing.get("product_id"),
        "listing_id": listing.get("id"),
        "category_id": listing.get("category_id"),
        "status": result.get("status"),
        "score": result.get("score") or 0,
        "payload_preview": result.get("payload") or {},
        "metadata_snapshot": result.get("discovery") or {},
        "conditional_snapshot": result.get("preflight") or {},
        "intelligence_snapshot": result.get("intelligence") or {},
        "blockers": result.get("blockers") or [],
        "warnings": result.get("warnings") or [],
        "recommendations": result.get("recommendations") or [],
    })
    return {"run_id":run_id,"saved":bool(saved.get("success"))}


@app.get("/api/publishing-lab/listing/{listing_id}")
async def publishing_lab_api(listing_id: str):
    listing=await s19_get_listing(listing_id)
    if not listing:
        return JSONResponse(status_code=404,content={"success":False,"error":"Anúncio não encontrado."})
    context=await s19_product_context(listing.get("product_id"))
    result=await s26_simulate(context, listing)
    run=await s26_store_run(listing,result)
    return {"version":APP_VERSION,**result,**run}


@app.get("/publishing-lab/listing/{listing_id}", response_class=HTMLResponse)
async def publishing_lab_page(listing_id: str):
    listing=await s19_get_listing(listing_id)
    if not listing:
        return HTMLResponse(shell("Publishing Lab","<div class='card'>Anúncio não encontrado.</div>"),status_code=404)
    context=await s19_product_context(listing.get("product_id"))
    result=await s26_simulate(context,listing)
    run=await s26_store_run(listing,result)
    blockers=''.join(f"<li><b>{s19e(x.get('code'))}</b>: {s19e(x.get('message'))}</li>" for x in result.get('blockers') or []) or '<li>Nenhum bloqueio.</li>'
    warnings=''.join(f"<li><b>{s19e(x.get('code'))}</b>: {s19e(x.get('message'))}</li>" for x in result.get('warnings') or []) or '<li>Nenhum alerta.</li>'
    cmp=result.get('comparison') or {}; disc=result.get('discovery') or {}
    content=f"""
<div class='grid'>
<div class='metric'><span>Status</span><strong>{'PRONTO' if result.get('success') else 'BLOQUEADO'}</strong></div>
<div class='metric'><span>Score</span><strong>{result.get('score')}</strong></div>
<div class='metric'><span>Atributos oficiais</span><strong>{disc.get('attributes_count')}</strong></div>
<div class='metric'><span>Run</span><strong>{s19e((run.get('run_id') or '')[:8])}</strong></div>
</div>
<div class='card'><h2>Bloqueios</h2><ul>{blockers}</ul><h2>Alertas</h2><ul>{warnings}</ul></div>
<div class='card'><h2>Comparador</h2><p><b>Enviados:</b> {s19e(', '.join(cmp.get('sent_attribute_ids') or []))}</p><p><b>Condicionais faltando:</b> {s19e(', '.join(cmp.get('missing_conditional_ids') or []))}</p><p><b>Desconhecidos:</b> {s19e(', '.join(cmp.get('unknown_attribute_ids') or []))}</p></div>
<div class='card'><h2>Estrutura</h2><p><b>Item:</b> {len(disc.get('item_attributes') or [])}</p><p><b>Variação:</b> {len(disc.get('variation_attributes') or [])}</p><p><b>Obrigatórios:</b> {len(disc.get('required_attributes') or [])}</p></div>
<div class='card'><a class='btn' href='/api/publishing-lab/listing/{listing_id}'>Relatório JSON</a><a class='btn' href='/product-master/{listing.get('product_id')}/listing'>Voltar ao anúncio</a></div>
"""
    return HTMLResponse(shell("Publishing Lab",content))


@app.post("/api/publishing-lab/listing/{listing_id}/publish")
async def publishing_lab_publish(listing_id: str, request: Request):
    listing=await s19_get_listing(listing_id)
    if not listing:
        return JSONResponse(status_code=404,content={"success":False,"error":"Anúncio não encontrado."})
    form=await request.form()
    if str(form.get("confirmation") or "").strip().upper() != "PUBLICAR":
        return JSONResponse(status_code=400,content={"success":False,"error":"Digite PUBLICAR para confirmar."})
    context=await s19_product_context(listing.get("product_id"))
    simulation=await s26_simulate(context,listing)
    if not simulation.get("success"):
        return JSONResponse(status_code=422,content={"success":False,"error":"Publishing Lab bloqueou a publicação.","simulation":simulation})
    payload=simulation.get("payload") or {}
    result=await ml_request("/items",method="POST",payload=payload)
    if not result.get("success"):
        try:
            await s25_record_error(context,listing,result,payload)
        except Exception:
            pass
        return JSONResponse(status_code=400,content={"success":False,"error":"Mercado Livre recusou o payload do Publishing Lab.","result":result,"payload_sent":payload})
    item=result.get("data") or {}
    await store.update("listings",f"id=eq.{quote(str(listing_id),safe='-')}",{
        "external_id":item.get("id"),"permalink":item.get("permalink"),"item_url":item.get("permalink"),
        "status":item.get("status") or "active","validation_status":"published","last_error":None,
        "payload":payload,"published_at":__import__('datetime').datetime.utcnow().isoformat(),
        "last_synced_at":__import__('datetime').datetime.utcnow().isoformat(),
    })
    return RedirectResponse(f"/listing-engine/{listing_id}",status_code=303)






# ==========================================================
# SPRINT 27.4 - ATTRIBUTE ROUTER HOTFIX
# Restaura classificação item x variação e roteamento do payload.
# ==========================================================

def s26_attr_tags(metadata):
    tags = metadata.get("tags") or {}
    if isinstance(tags, str):
        try:
            parsed = json.loads(tags)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return tags if isinstance(tags, dict) else {}


def s26_attr_raw(metadata):
    raw = metadata.get("raw_data") or {}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return raw if isinstance(raw, dict) else {}


def s26_attr_location(metadata):
    tags = s26_attr_tags(metadata)
    raw = s26_attr_raw(metadata)

    attribute_id = str(
        metadata.get("attribute_id")
        or metadata.get("id")
        or ""
    ).upper()

    # Marcadores oficiais/semioficiais de atributos de variação.
    variation_flags = (
        metadata.get("allow_variations"),
        tags.get("allow_variations"),
        tags.get("variation_attribute"),
        tags.get("defines_picture"),
        raw.get("allow_variations"),
        raw.get("variation_attribute"),
    )

    # Alguns atributos são tipicamente de variação mesmo quando os metadados
    # antigos não carregam todas as tags.
    common_variation_ids = {
        "COLOR",
        "MAIN_COLOR",
        "SIZE",
        "VOLTAGE",
        "PATTERN_NAME",
        "FABRIC_DESIGN",
        "HAND_ORIENTATION",
    }

    if any(bool(flag) for flag in variation_flags):
        return "variation"

    if attribute_id in common_variation_ids and (
        tags.get("allow_variations")
        or tags.get("defines_picture")
        or metadata.get("allow_variations")
    ):
        return "variation"

    return "item"


def s26_is_variation(metadata):
    return s26_attr_location(metadata) == "variation"


def s26_is_item(metadata):
    return s26_attr_location(metadata) == "item"


def s26_split_item_variation(attributes, metadata_map):
    item_attributes = []
    variation_attributes = []

    for attribute in attributes or []:
        attribute_id = str(attribute.get("id") or "").upper()
        metadata = metadata_map.get(attribute_id) or {
            "attribute_id": attribute_id
        }

        if s26_is_variation(metadata):
            variation_attributes.append(attribute)
        else:
            item_attributes.append(attribute)

    return item_attributes, variation_attributes


def s26_build_attribute_contract(metadata):
    tags = s26_attr_tags(metadata)
    values = metadata.get("values") or []

    if isinstance(values, str):
        try:
            parsed = json.loads(values)
            values = parsed if isinstance(parsed, list) else []
        except Exception:
            values = []

    return {
        "attribute_id": str(
            metadata.get("attribute_id")
            or metadata.get("id")
            or ""
        ).upper(),
        "name": metadata.get("name"),
        "location": s26_attr_location(metadata),
        "required": bool(
            metadata.get("required")
            or metadata.get("catalog_required")
            or tags.get("required")
            or tags.get("catalog_required")
            or tags.get("conditional_required")
        ),
        "conditional_required": bool(tags.get("conditional_required")),
        "catalog_required": bool(
            metadata.get("catalog_required")
            or tags.get("catalog_required")
        ),
        "value_type": metadata.get("value_type"),
        "value_strategy": (
            "value_id_preferred"
            if values or str(metadata.get("value_type") or "").lower() in {
                "boolean", "list"
            }
            else "value_name"
        ),
        "allowed_values": values,
    }


def s26_validate_payload_contract(payload, metadata_map, conditional_ids=None):
    conditional_ids = {
        str(item or "").upper()
        for item in (conditional_ids or [])
    }

    sent_item_ids = {
        str(item.get("id") or "").upper()
        for item in (payload.get("attributes") or [])
        if item.get("id")
    }

    sent_variation_ids = set()
    for variation in payload.get("variations") or []:
        for item in variation.get("attribute_combinations") or []:
            if item.get("id"):
                sent_variation_ids.add(str(item.get("id")).upper())
        for item in variation.get("attributes") or []:
            if item.get("id"):
                sent_variation_ids.add(str(item.get("id")).upper())

    sent_all = sent_item_ids | sent_variation_ids
    official_ids = set(metadata_map.keys())

    blockers = []
    warnings = []

    for attribute_id, metadata in metadata_map.items():
        contract = s26_build_attribute_contract(metadata)

        if contract.get("required") and attribute_id not in sent_all:
            blockers.append({
                "code": "required_attribute_missing",
                "attribute": attribute_id,
                "message": f"O atributo obrigatório {attribute_id} não foi enviado.",
                "location": contract.get("location"),
            })

        if (
            attribute_id in sent_item_ids
            and contract.get("location") == "variation"
        ):
            warnings.append({
                "code": "attribute_wrong_location",
                "attribute": attribute_id,
                "message": f"{attribute_id} deveria estar em variation.",
            })

    for attribute_id in conditional_ids:
        if attribute_id not in sent_all:
            blockers.append({
                "code": "conditional_required_missing",
                "attribute": attribute_id,
                "message": f"O atributo condicional {attribute_id} não foi enviado.",
            })

    for attribute_id in sorted(sent_all - official_ids):
        blockers.append({
            "code": "unknown_attribute",
            "attribute": attribute_id,
            "message": f"O atributo {attribute_id} não existe nos metadados oficiais.",
        })

    return {
        "valid": len(blockers) == 0,
        "item_attribute_ids": sorted(sent_item_ids),
        "variation_attribute_ids": sorted(sent_variation_ids),
        "blockers": blockers,
        "warnings": warnings,
    }


# ==========================================================
# SPRINT 27.3 - MISSING SIMULATOR HOTFIX
# Implementação compatível de s26_simulate_listing.
# ==========================================================

async def s26_simulate_listing(context, listing):
    build = await s26_build_payload(context, listing)
    payload = build.get("payload") or {}
    discovery = build.get("discovery") or {}

    try:
        preflight = await s24_metadata_preflight(context, listing)
    except Exception as exc:
        preflight = {
            "success": False,
            "official_attribute_ids": [],
            "conditional_attribute_ids": [],
            "blockers": [],
            "warnings": [{
                "code": "preflight_runtime_error",
                "message": str(exc),
            }],
        }

    try:
        intelligence = await s25_intelligence_assessment(context, listing)
    except Exception as exc:
        intelligence = {
            "success": False,
            "blockers": [],
            "warnings": [],
            "recommendations": [{
                "action": "inspect_runtime",
                "message": str(exc),
            }],
        }

    conditional_ids = preflight.get("conditional_attribute_ids") or []
    official_ids = preflight.get("official_attribute_ids") or []

    comparison = s26_compare_payload(payload, official_ids, conditional_ids)

    blockers = list(preflight.get("blockers") or [])
    warnings = list(preflight.get("warnings") or [])
    recommendations = list(intelligence.get("recommendations") or [])

    for aid in comparison.get("unknown_attribute_ids") or []:
        blockers.append({
            "code": "unknown_attribute",
            "message": f"O atributo {aid} não existe nos metadados oficiais da categoria.",
            "attribute": aid,
        })

    for aid in comparison.get("missing_conditional_ids") or []:
        blockers.append({
            "code": "conditional_required_missing",
            "message": f"O atributo condicional {aid} ainda está faltando.",
            "attribute": aid,
        })

    variation_attrs = build.get("variation_attributes") or []
    if variation_attrs:
        warnings.append({
            "code": "variation_payload_generated",
            "message": "Atributos de variação foram movidos para attribute_combinations.",
            "attributes": [item.get("id") for item in variation_attrs],
        })

    score = 100
    score -= min(80, len(blockers) * 20)
    score -= min(20, len(warnings) * 5)
    score = max(0, score)

    return {
        "success": len(blockers) == 0,
        "version": APP_VERSION,
        "score": score,
        "status": "ready" if not blockers else "blocked",
        "payload": payload,
        "discovery": discovery,
        "comparison": comparison,
        "preflight": preflight,
        "intelligence": intelligence,
        "blockers": blockers,
        "warnings": warnings,
        "recommendations": recommendations,
    }


# ==========================================================
# SPRINT 27 - MARKETPLACE RULES ENGINE
# Converte metadados oficiais e condicionais em árvore de decisão.
# ==========================================================

def s27_sha256(value):
    import hashlib
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def s272_dict(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def s272_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def s27_dedupe_issues(items):
    output = []
    seen = set()
    for item in items or []:
        code = str(item.get("code") or "")
        attribute = str(item.get("attribute") or "")
        attrs = tuple(sorted(str(x) for x in (item.get("attributes") or [])))
        message = str(item.get("message") or "")
        key = (code, attribute, attrs, message)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def s27_metadata_required(attr):
    tags = s272_dict(attr.get("tags"))
    return bool(
        attr.get("required")
        or attr.get("catalog_required")
        or tags.get("required")
        or tags.get("catalog_required")
        or tags.get("conditional_required")
    )


def s27_value_strategy(attr):
    values = s272_list(attr.get("values"))
    value_type = str(attr.get("value_type") or "").lower()
    if values:
        return "value_id_preferred"
    if value_type in {"boolean", "list"}:
        return "value_id_preferred"
    return "value_name"


def s27_attribute_contract(attr):
    aid = str(attr.get("attribute_id") or "").upper()
    return {
        "id": aid,
        "name": attr.get("name"),
        "required": s27_metadata_required(attr),
        "catalog_required": bool(attr.get("catalog_required")),
        "conditional_required": bool((attr.get("tags") or {}).get("conditional_required")),
        "location": s26_attr_location(attr),
        "value_strategy": s27_value_strategy(attr),
        "value_type": attr.get("value_type"),
        "allowed_values": attr.get("values") or [],
    }


async def s27_build_contract(context, listing):
    product = context.get("product") or {}
    category_id = listing.get("category_id")
    diagnostics = []

    try:
        discovery = await s26_category_discovery(category_id)
    except Exception as exc:
        diagnostics.append({"stage": "category_discovery", "error": str(exc)})
        discovery = {
            "success": False,
            "category_id": category_id,
            "raw_attributes": [],
            "item_attributes": [],
            "variation_attributes": [],
            "required_attributes": [],
        }

    try:
        preflight = await s24_metadata_preflight(context, listing)
    except Exception as exc:
        diagnostics.append({"stage": "metadata_preflight", "error": str(exc)})
        preflight = {
            "success": False,
            "conditional_attribute_ids": [],
            "sent_attribute_ids": [],
            "conditional_validation": {},
            "blockers": [],
            "warnings": [],
        }

    try:
        intelligence = await s25_intelligence_assessment(context, listing)
    except Exception as exc:
        diagnostics.append({"stage": "intelligence_assessment", "error": str(exc)})
        intelligence = {"success": False, "rules": [], "blockers": [], "recommendations": []}

    attrs = discovery.get("raw_attributes") or []
    contracts = {}

    for attr in attrs:
        try:
            aid = str(attr.get("attribute_id") or "").upper()
            if aid:
                contracts[aid] = s27_attribute_contract(attr)
        except Exception as exc:
            diagnostics.append({
                "stage": "attribute_contract",
                "attribute_id": str(attr.get("attribute_id") or ""),
                "error": str(exc),
            })

    conditional_ids = {
        str(x).upper()
        for x in (preflight.get("conditional_attribute_ids") or [])
    }

    for aid in conditional_ids:
        if aid in contracts:
            contracts[aid]["conditional_required"] = True
            contracts[aid]["required"] = True

    sent_ids = {
        str(x).upper()
        for x in (preflight.get("sent_attribute_ids") or [])
    }

    decisions = []
    required_actions = []

    for aid, contract in contracts.items():
        present = aid in sent_ids
        if contract.get("required") and not present:
            action = {
                "action": "provide_attribute",
                "attribute_id": aid,
                "message": f"Informe o atributo obrigatório {aid}.",
                "location": contract.get("location"),
                "value_strategy": contract.get("value_strategy"),
            }
            required_actions.append(action)
            decisions.append({
                "rule_key": f"REQUIRE_{aid}",
                "input_state": {"present": present},
                "outcome": "blocked",
                "required_actions": [action],
                "explanation": f"{aid} é obrigatório para este payload.",
                "confidence": 100,
            })

    gtin_contract = contracts.get("GTIN") or {}
    empty_contract = contracts.get("EMPTY_GTIN_REASON") or {}

    try:
        values = await s21_product_values(product.get("id"), category_id)
    except Exception as exc:
        diagnostics.append({"stage": "product_values", "error": str(exc)})
        values = {}

    gtin_row = values.get("GTIN") or values.get("gtin") or {}
    reason_row = values.get("EMPTY_GTIN_REASON") or values.get("empty_gtin_reason") or {}

    gtin_value = gtin_row.get("value_name") or gtin_row.get("value_id")
    has_valid_gtin = s212_valid_gtin(gtin_value)
    has_reason = bool(reason_row.get("value_id") or reason_row.get("value_name"))
    gtin_conditional = "GTIN" in conditional_ids
    learned_gtin_required = any(
        str(row.get("rule_key") or "").upper() == "GTIN_REQUIRED"
        for row in (intelligence.get("rules") or [])
        if isinstance(row, dict)
    )

    if gtin_conditional or learned_gtin_required:
        if not has_valid_gtin:
            required_actions.append({
                "action": "provide_real_gtin",
                "attribute_id": "GTIN",
                "message": "Informe um GTIN real e válido do produto.",
                "location": gtin_contract.get("location") or "item",
                "value_strategy": "value_name",
            })

        decisions.append({
            "rule_key": "GTIN_RESOLUTION",
            "input_state": {
                "gtin_valid": has_valid_gtin,
                "empty_gtin_reason_present": has_reason,
                "empty_gtin_reason_supported": bool(empty_contract),
                "conditional_requires_gtin": gtin_conditional,
                "learned_requires_gtin": learned_gtin_required,
            },
            "outcome": "ready" if has_valid_gtin else "blocked",
            "required_actions": [] if has_valid_gtin else [{
                "action": "provide_real_gtin",
                "attribute_id": "GTIN",
            }],
            "explanation": (
                "GTIN válido presente."
                if has_valid_gtin
                else "A validação condicional ou o aprendizado real exige GTIN; "
                     "EMPTY_GTIN_REASON não substitui o código neste caso."
            ),
            "confidence": 100,
        })

    payload_contract = {
        "category_id": category_id,
        "family_name_required": True,
        "attribute_contracts": contracts,
        "item_attribute_ids": sorted(
            aid for aid, c in contracts.items() if c.get("location") == "item"
        ),
        "variation_attribute_ids": sorted(
            aid for aid, c in contracts.items() if c.get("location") == "variation"
        ),
        "conditional_attribute_ids": sorted(conditional_ids),
    }

    decision_tree = {
        "status": "ready" if not required_actions else "blocked",
        "required_actions": required_actions,
        "decisions": decisions,
        "gtin": {
            "valid": has_valid_gtin,
            "empty_reason_present": has_reason,
            "conditional_required": gtin_conditional,
            "learned_required": learned_gtin_required,
        },
        "diagnostics": diagnostics,
    }

    fingerprint = s27_sha256({
        "category_id": category_id,
        "brand": product.get("brand"),
        "payload_contract": payload_contract,
        "conditional_ids": sorted(conditional_ids),
    })

    return {
        "success": not required_actions,
        "category_id": category_id,
        "brand": product.get("brand"),
        "fingerprint": fingerprint,
        "decision_tree": decision_tree,
        "official_metadata": discovery,
        "conditional_metadata": preflight.get("conditional_validation"),
        "payload_contract": payload_contract,
        "required_actions": required_actions,
        "decisions": decisions,
        "diagnostics": diagnostics,
    }


async def s27_save_contract(context, listing, result):
    product = context.get("product") or {}
    category_id = str(listing.get("category_id") or "")
    brand = str(product.get("brand") or "").strip()
    fingerprint = str(result.get("fingerprint") or "")

    payload = {
        "company_id": DEFAULT_COMPANY_ID,
        "marketplace": "mercado_livre",
        "category_id": category_id,
        "brand": brand or None,
        "domain_id": None,
        "fingerprint": fingerprint,
        "decision_tree": result.get("decision_tree") or {},
        "official_metadata": result.get("official_metadata") or {},
        "conditional_metadata": result.get("conditional_metadata") or {},
        "payload_contract": result.get("payload_contract") or {},
        "active": True,
    }

    # Não usa on_conflict com colunas nullable/expression index.
    # O PostgREST não consegue resolver esse tipo de índice como constraint.
    query = (
        "select=*&marketplace=eq.mercado_livre"
        + "&category_id=eq." + quote(category_id, safe="-_")
        + "&fingerprint=eq." + quote(fingerprint, safe="")
        + ("&brand=eq." + quote(brand, safe="-_ ") if brand else "&brand=is.null")
        + "&domain_id=is.null&limit=1"
    )

    existing_result = await store.select("marketplace_rule_snapshots", query)
    existing_rows = existing_result.get("data") or []
    existing = existing_rows[0] if existing_rows else None

    if existing:
        snapshot_id = existing.get("id")
        saved = await store.update(
            "marketplace_rule_snapshots",
            "id=eq." + quote(str(snapshot_id), safe="-"),
            payload,
        )
    else:
        saved = await store.insert("marketplace_rule_snapshots", payload)
        rows = saved.get("data") or []
        if isinstance(rows, dict):
            rows = [rows]
        snapshot_id = (rows[0] if rows else {}).get("id")

    if not saved.get("success"):
        return {
            "success": False,
            "snapshot_id": snapshot_id if 'snapshot_id' in locals() else None,
            "result": saved,
            "error": saved.get("error") or saved.get("raw"),
        }

    # Evita multiplicar as mesmas decisões a cada abertura da página.
    if snapshot_id:
        await store.delete(
            "marketplace_rule_decisions",
            "snapshot_id=eq." + quote(str(snapshot_id), safe="-")
        )
        for decision in result.get("decisions") or []:
            await store.insert("marketplace_rule_decisions", {
                "snapshot_id": snapshot_id,
                "rule_key": decision.get("rule_key"),
                "input_state": decision.get("input_state") or {},
                "outcome": decision.get("outcome"),
                "required_actions": decision.get("required_actions") or [],
                "explanation": decision.get("explanation"),
                "confidence": decision.get("confidence") or 100,
            })

    return {
        "success": True,
        "snapshot_id": snapshot_id,
        "result": saved,
    }


async def s27_rules_engine(context, listing):
    contract = await s27_build_contract(context, listing)

    try:
        saved = await s27_save_contract(context, listing, contract)
    except Exception as exc:
        saved = {
            "success": False,
            "snapshot_id": None,
            "error": str(exc),
        }

    simulation = await s26_simulate_listing(context, listing)
    simulation["blockers"] = s27_dedupe_issues(simulation.get("blockers"))
    simulation["warnings"] = s27_dedupe_issues(simulation.get("warnings"))

    for action in contract.get("required_actions") or []:
        simulation["blockers"].append({
            "code": "rules_engine_required_action",
            "message": action.get("message"),
            "attribute": action.get("attribute_id"),
            "location": action.get("location"),
        })

    simulation["blockers"] = s27_dedupe_issues(simulation.get("blockers"))
    simulation["success"] = len(simulation["blockers"]) == 0
    simulation["status"] = "ready" if simulation["success"] else "blocked"
    simulation["score"] = max(
        0,
        100
        - min(80, len(simulation["blockers"]) * 20)
        - min(20, len(simulation.get("warnings") or []) * 5)
    )

    return {
        "success": simulation["success"],
        "version": APP_VERSION,
        "contract": contract,
        "simulation": simulation,
        "snapshot_id": saved.get("snapshot_id"),
        "saved": saved.get("success"),
        "save_error": saved.get("error") if not saved.get("success") else None,
    }


@app.get("/api/marketplace-rules/listing/{listing_id}")
async def marketplace_rules_api(listing_id: str):
    listing = await s19_get_listing(listing_id)
    if not listing:
        return JSONResponse(status_code=404, content={
            "success": False,
            "error": "Anúncio não encontrado.",
        })

    context = await s19_product_context(listing.get("product_id"))
    if not context:
        return JSONResponse(status_code=404, content={
            "success": False,
            "error": "Produto não encontrado.",
        })

    try:
        return await s27_rules_engine(context, listing)
    except Exception as exc:
        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "version": APP_VERSION,
                "error": "Rules Engine runtime error",
                "error_type": type(exc).__name__,
                "detail": str(exc),
                "listing_id": listing_id,
            },
        )


@app.get("/marketplace-rules/listing/{listing_id}", response_class=HTMLResponse)
async def marketplace_rules_page(listing_id: str):
    listing = await s19_get_listing(listing_id)
    if not listing:
        return HTMLResponse(
            shell("Marketplace Rules Engine", "<div class='card'>Anúncio não encontrado.</div>"),
            status_code=404,
        )

    context = await s19_product_context(listing.get("product_id"))

    try:
        result = await s27_rules_engine(context, listing)
    except Exception as exc:
        detail = s19e(str(exc))
        error_type = s19e(type(exc).__name__)
        content = f"""
<div class='card'>
<h2>Rules Engine — diagnóstico</h2>
<p><b>Tipo:</b> {error_type}</p>
<p><b>Detalhe:</b> {detail}</p>
<p>Abra o JSON técnico para copiar o diagnóstico completo.</p>
<a class='btn' href='/api/marketplace-rules/listing/{listing_id}'>Ver JSON técnico</a>
<a class='btn' href='/product-master/{listing.get("product_id")}/listing'>Voltar ao anúncio</a>
</div>
"""
        return HTMLResponse(shell("Marketplace Rules Engine", content), status_code=200)

    contract = result.get("contract") or {}
    simulation = result.get("simulation") or {}
    tree = contract.get("decision_tree") or {}

    actions_html = "".join(
        f"<li><b>{s19e(item.get('attribute_id') or item.get('action'))}</b>: "
        f"{s19e(item.get('message'))} "
        f"<small>({s19e(item.get('location') or 'item')})</small></li>"
        for item in (contract.get("required_actions") or [])
    ) or "<li>Nenhuma ação obrigatória.</li>"

    decisions_html = "".join(
        f"""<tr>
<td>{s19e(item.get('rule_key'))}</td>
<td>{s19e(item.get('outcome'))}</td>
<td>{s19e(item.get('explanation'))}</td>
<td>{s19e(item.get('confidence'))}%</td>
</tr>"""
        for item in (contract.get("decisions") or [])
    ) or "<tr><td colspan='4'>Nenhuma decisão.</td></tr>"

    payload_contract = contract.get("payload_contract") or {}

    content = f"""
<div class='grid'>
  <div class='metric'><span>Status</span><strong>{'PRONTO' if result.get('success') else 'BLOQUEADO'}</strong></div>
  <div class='metric'><span>Score</span><strong>{simulation.get('score')}</strong></div>
  <div class='metric'><span>Snapshot</span><strong>{s19e((result.get('snapshot_id') or '')[:8])}</strong></div>
  <div class='metric'><span>Categoria</span><strong>{s19e(contract.get('category_id'))}</strong></div>
</div>

<div class='card'>
<h2>Ações obrigatórias</h2>
<ul>{actions_html}</ul>
</div>

<div class='card'>
<h2>Árvore de decisão</h2>
<table>
<thead><tr><th>Regra</th><th>Resultado</th><th>Explicação</th><th>Confiança</th></tr></thead>
<tbody>{decisions_html}</tbody>
</table>
</div>

<div class='card'>
<h2>Contrato do payload</h2>
<p><b>Atributos de item:</b> {len(payload_contract.get('item_attribute_ids') or [])}</p>
<p><b>Atributos de variação:</b> {len(payload_contract.get('variation_attribute_ids') or [])}</p>
<p><b>Condicionais:</b> {s19e(', '.join(payload_contract.get('conditional_attribute_ids') or []))}</p>
<p><b>Snapshot salvo:</b> {'SIM' if result.get('saved') else 'NÃO'}</p>
<p><b>Erro ao salvar:</b> {s19e(result.get('save_error') or '-')}</p>
<p><b>Diagnósticos:</b> {s19e(json.dumps(contract.get('diagnostics') or [], ensure_ascii=False))}</p>
</div>

<div class='card'>
<a class='btn' href='/publishing-lab/listing/{listing_id}'>Publishing Lab</a>
<a class='btn' href='/api/marketplace-rules/listing/{listing_id}'>Ver JSON técnico</a>
<a class='btn' href='/product-master/{listing.get("product_id")}/listing'>Voltar ao anúncio</a>
</div>
"""
    return HTMLResponse(shell("Marketplace Rules Engine", content))


async def s26_build_payload(context, listing):
    payload = s19_build_ml_payload(context, listing, mode="user_product")
    payload["attributes"] = await s21_payload_attributes(
        context["product"].get("id"),
        listing.get("category_id"),
        payload.get("attributes"),
    )

    discovery = await s26_category_discovery(listing.get("category_id"))
    metadata_map = {
        str(item.get("attribute_id") or "").upper(): item
        for item in (discovery.get("raw_attributes") or [])
        if item.get("attribute_id")
    }

    item_attrs, variation_attrs = s26_split_item_variation(
        payload.get("attributes") or [],
        metadata_map,
    )

    payload["attributes"] = item_attrs

    if variation_attrs:
        payload["variations"] = [{
            "price": payload.get("price"),
            "available_quantity": payload.get("available_quantity"),
            "attribute_combinations": variation_attrs,
            "picture_ids": [],
        }]
    else:
        payload.pop("variations", None)

    contract_validation = s26_validate_payload_contract(
        payload,
        metadata_map,
        [],
    )

    return {
        "payload": payload,
        "item_attributes": item_attrs,
        "variation_attributes": variation_attrs,
        "discovery": discovery,
        "metadata_map": metadata_map,
        "contract_validation": contract_validation,
    }


def s26_compare_payload(payload, official_ids, conditional_ids):
    sent = {
        str(item.get("id") or "").upper()
        for item in (payload.get("attributes") or [])
        if item.get("id")
    }
    official = {str(x).upper() for x in official_ids or []}
    conditional = {str(x).upper() for x in conditional_ids or []}

    return {
        "sent_attribute_ids": sorted(sent),
        "unknown_attribute_ids": sorted(sent - official),
        "missing_conditional_ids": sorted(conditional - sent),
        "valid": not (sent - official) and not (conditional - sent),
    }


async def s26_category_discovery(category_id):
    await s21_sync_category(category_id)
    attrs = await s21_category_attrs(category_id)

    item_attributes = []
    variation_attributes = []
    required_attributes = []
    optional_attributes = []

    for attr in attrs:
        location = s26_attr_location(attr) if "s26_attr_location" in globals() else "item"
        row = {
            "attribute_id": attr.get("attribute_id"),
            "name": attr.get("name"),
            "required": bool(attr.get("required") or attr.get("catalog_required")),
            "catalog_required": bool(attr.get("catalog_required")),
            "value_type": attr.get("value_type"),
            "values_count": len(attr.get("values") or []),
            "location": location,
        }

        if location == "variation":
            variation_attributes.append(row)
        else:
            item_attributes.append(row)

        if row["required"]:
            required_attributes.append(row)
        else:
            optional_attributes.append(row)

    return {
        "success": True,
        "category_id": category_id,
        "attributes_count": len(attrs),
        "required_attributes": required_attributes,
        "optional_attributes": optional_attributes,
        "item_attributes": item_attributes,
        "variation_attributes": variation_attributes,
        "raw_attributes": attrs,
    }


# ==========================================================
# SPRINT 28 - MARKETPLACE INSPECTOR
# Descobre exatamente o que o Mercado Livre exige antes da publicação.
# ==========================================================

def s28_json_dict(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def s28_json_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def s28_attribute_requirement(attr):
    tags = s28_json_dict(attr.get("tags"))
    values = s28_json_list(attr.get("values"))
    attribute_id = str(
        attr.get("attribute_id")
        or attr.get("id")
        or ""
    ).upper()

    required = bool(
        attr.get("required")
        or attr.get("catalog_required")
        or tags.get("required")
        or tags.get("catalog_required")
        or tags.get("conditional_required")
    )

    if values:
        accepted_format = "value_id ou valor listado"
    else:
        accepted_format = str(attr.get("value_type") or "value_name")

    return {
        "field": attribute_id,
        "name": attr.get("name") or attribute_id,
        "required": required,
        "catalog_required": bool(attr.get("catalog_required") or tags.get("catalog_required")),
        "conditional_required": bool(tags.get("conditional_required")),
        "location": s26_attr_location(attr),
        "accepted_format": accepted_format,
        "accepted_values": values,
        "value_type": attr.get("value_type"),
        "source": f"/categories/{{category_id}}/attributes",
    }


async def s28_build_payload_preview(context, listing):
    payload = s19_build_ml_payload(context, listing, mode="user_product")
    payload["attributes"] = await s21_payload_attributes(
        context["product"].get("id"),
        listing.get("category_id"),
        payload.get("attributes"),
    )
    routed = await s331_apply_identifier_routing(context, listing, payload)
    return routed.get("payload") or payload


async def s28_conditional_check(category_id, payload):
    path = f"/categories/{quote(str(category_id), safe='-_')}/attributes/conditional"
    first = await ml_request(path, method="POST", payload=payload)

    if first.get("success"):
        return {
            "success": True,
            "request_shape": "full_item",
            "result": first,
        }

    second = await ml_request(
        path,
        method="POST",
        payload={"attributes": payload.get("attributes") or []},
    )

    return {
        "success": bool(second.get("success")),
        "request_shape": "attributes_only",
        "result": second if second.get("success") else first,
        "fallback_result": second,
    }


def s28_conditional_required_ids(conditional):
    result = conditional.get("result") or {}
    data = result.get("data") or {}
    required = data.get("required_attributes") or []
    ids = []

    for item in required:
        if isinstance(item, dict) and item.get("id"):
            ids.append(str(item.get("id")).upper())

    return sorted(set(ids))


def s28_current_attribute_ids(payload):
    ids = {
        str(item.get("id") or "").upper()
        for item in (payload.get("attributes") or [])
        if item.get("id")
    }

    for variation in payload.get("variations") or []:
        for item in variation.get("attribute_combinations") or []:
            if item.get("id"):
                ids.add(str(item.get("id")).upper())
        for item in variation.get("attributes") or []:
            if item.get("id"):
                ids.add(str(item.get("id")).upper())

    return sorted(ids)


async def s28_inspect_listing(listing_id):
    listing = await s19_get_listing(listing_id)
    if not listing:
        return {
            "success": False,
            "status_code": 404,
            "error": "Anúncio não encontrado.",
        }

    context = await s19_product_context(listing.get("product_id"))
    if not context:
        return {
            "success": False,
            "status_code": 404,
            "error": "Produto não encontrado.",
        }

    category_id = listing.get("category_id")

    category_result = await ml_request(
        f"/categories/{quote(str(category_id), safe='-_')}"
    )
    attrs_result = await ml_request(
        f"/categories/{quote(str(category_id), safe='-_')}/attributes"
    )
    listing_types_result = await ml_request("/sites/MLB/listing_types")

    payload = await s28_build_payload_preview(context, listing)
    conditional = await s28_conditional_check(category_id, payload)

    category_data = category_result.get("data") or {}
    raw_attributes = attrs_result.get("data") or []
    requirements = []

    for attr in raw_attributes:
        requirement = s28_attribute_requirement(attr)
        requirement["source"] = f"/categories/{category_id}/attributes"
        requirements.append(requirement)

    conditional_ids = s28_conditional_required_ids(conditional)
    current_ids = s28_current_attribute_ids(payload)

    by_id = {item.get("field"): item for item in requirements}
    for attribute_id in conditional_ids:
        if attribute_id in by_id:
            by_id[attribute_id]["required"] = True
            by_id[attribute_id]["conditional_required"] = True
            by_id[attribute_id]["source"] = (
                f"/categories/{category_id}/attributes/conditional"
            )
        else:
            requirements.append({
                "field": attribute_id,
                "name": attribute_id,
                "required": True,
                "catalog_required": False,
                "conditional_required": True,
                "location": "item",
                "accepted_format": "consultar metadados",
                "accepted_values": [],
                "value_type": None,
                "source": f"/categories/{category_id}/attributes/conditional",
            })

    missing = sorted(
        item.get("field")
        for item in requirements
        if item.get("required") and item.get("field") not in current_ids
    )

    invalid_or_unknown = sorted(
        attribute_id
        for attribute_id in current_ids
        if attribute_id not in {
            str(item.get("field") or "").upper()
            for item in requirements
        }
    )

    exact_requirements = {
        "category_id": category_id,
        "category_name": category_data.get("name"),
        "domain_id": category_data.get("domain_id"),
        "current_payload_attribute_ids": current_ids,
        "conditional_required_ids": conditional_ids,
        "missing_required_ids": missing,
        "unknown_sent_ids": invalid_or_unknown,
        "listing_type_id": listing.get("listing_type_id") or "gold_special",
        "listing_types_available": listing_types_result.get("data") or [],
        "can_publish": not missing and not invalid_or_unknown,
        "requirements": requirements,
    }

    run_id = str(uuid.uuid4())
    run_payload = {
        "id": run_id,
        "company_id": DEFAULT_COMPANY_ID,
        "marketplace": "mercado_livre",
        "product_id": listing.get("product_id"),
        "listing_id": listing.get("id"),
        "category_id": category_id,
        "status": "ready" if exact_requirements["can_publish"] else "blocked",
        "category_snapshot": category_data,
        "attributes_snapshot": raw_attributes,
        "conditional_snapshot": conditional,
        "listing_types_snapshot": listing_types_result.get("data") or [],
        "payload_snapshot": payload,
        "requirements_snapshot": exact_requirements,
    }
    saved = await store.insert("marketplace_inspector_runs", run_payload)

    if saved.get("success"):
        for requirement in requirements:
            await store.insert("marketplace_inspector_findings", {
                "run_id": run_id,
                "finding_type": (
                    "conditional_required"
                    if requirement.get("conditional_required")
                    else "required"
                    if requirement.get("required")
                    else "optional"
                ),
                "field_name": requirement.get("field"),
                "required": bool(requirement.get("required")),
                "accepted_format": requirement.get("accepted_format"),
                "accepted_values": requirement.get("accepted_values") or [],
                "location": requirement.get("location"),
                "source_endpoint": requirement.get("source"),
                "evidence": requirement,
            })

    return {
        "success": True,
        "version": APP_VERSION,
        "run_id": run_id,
        "saved": bool(saved.get("success")),
        "listing": listing,
        "product": context.get("product"),
        "category": category_result,
        "attributes": attrs_result,
        "conditional": conditional,
        "listing_types": listing_types_result,
        "payload_preview": payload,
        "inspection": exact_requirements,
    }


@app.get("/api/marketplace-inspector/listing/{listing_id}")
async def marketplace_inspector_api(listing_id: str):
    result = await s28_inspect_listing(listing_id)
    if not result.get("success"):
        return JSONResponse(
            status_code=int(result.get("status_code") or 400),
            content=result,
        )
    return result


@app.get("/marketplace-inspector/listing/{listing_id}", response_class=HTMLResponse)
async def marketplace_inspector_page(listing_id: str):
    result = await s28_inspect_listing(listing_id)
    if not result.get("success"):
        return HTMLResponse(
            shell(
                "Marketplace Inspector",
                f"<div class='card'><h2>Erro</h2><p>{s19e(result.get('error'))}</p></div>",
            ),
            status_code=int(result.get("status_code") or 400),
        )

    inspection = result.get("inspection") or {}
    requirements = inspection.get("requirements") or []

    rows = ""
    for item in requirements:
        if not item.get("required") and not item.get("conditional_required"):
            continue

        values = item.get("accepted_values") or []
        values_text = ", ".join(
            str(option.get("name") or option.get("id") or "")
            for option in values[:6]
            if isinstance(option, dict)
        )

        rows += f"""
<tr>
<td>{s19e(item.get('field'))}</td>
<td>{s19e(item.get('name'))}</td>
<td>{'SIM' if item.get('required') else 'NÃO'}</td>
<td>{'SIM' if item.get('conditional_required') else 'NÃO'}</td>
<td>{s19e(item.get('location'))}</td>
<td>{s19e(item.get('accepted_format'))}</td>
<td>{s19e(values_text or '-')}</td>
<td>{s19e(item.get('source'))}</td>
</tr>
"""

    missing = inspection.get("missing_required_ids") or []
    unknown = inspection.get("unknown_sent_ids") or []

    missing_html = "".join(
        f"<li>{s19e(item)}</li>" for item in missing
    ) or "<li>Nenhum campo obrigatório faltando.</li>"

    unknown_html = "".join(
        f"<li>{s19e(item)}</li>" for item in unknown
    ) or "<li>Nenhum atributo desconhecido no payload.</li>"

    content = f"""
<div class='grid'>
  <div class='metric'><span>Status</span><strong>{'LIBERADO' if inspection.get('can_publish') else 'BLOQUEADO'}</strong></div>
  <div class='metric'><span>Categoria</span><strong>{s19e(inspection.get('category_id'))}</strong></div>
  <div class='metric'><span>Condicionais</span><strong>{len(inspection.get('conditional_required_ids') or [])}</strong></div>
  <div class='metric'><span>Faltando</span><strong>{len(missing)}</strong></div>
</div>

<div class='card'>
<h2>Exigências exatas do Mercado Livre</h2>
<p><b>Categoria:</b> {s19e(inspection.get('category_name') or inspection.get('category_id'))}</p>
<p><b>Listing type atual:</b> {s19e(inspection.get('listing_type_id'))}</p>
<table>
<thead>
<tr>
<th>Campo</th>
<th>Nome</th>
<th>Obrigatório</th>
<th>Condicional</th>
<th>Local</th>
<th>Formato aceito</th>
<th>Valores aceitos</th>
<th>Fonte oficial</th>
</tr>
</thead>
<tbody>{rows}</tbody>
</table>
</div>

<div class='card'>
<h2>Campos que ainda faltam</h2>
<ul>{missing_html}</ul>
<h2>Atributos enviados que não existem na categoria</h2>
<ul>{unknown_html}</ul>
</div>

<div class='card'>
<h2>Payload atual analisado</h2>
<pre>{s19e(json.dumps(result.get('payload_preview') or {}, ensure_ascii=False, indent=2))}</pre>
</div>

<div class='card'>
<a class='btn' href='/api/marketplace-inspector/listing/{listing_id}'>Ver JSON técnico completo</a>
<a class='btn' href='/product-master/{result.get("listing", {}).get("product_id")}/listing'>Voltar ao anúncio</a>
</div>
"""
    return HTMLResponse(shell("Marketplace Inspector", content))


# ==========================================================
# SPRINT 29 - MARKETPLACE KNOWLEDGE ENGINE
# Consolida metadados oficiais, validação condicional e histórico real.
# ==========================================================

def s29_hash(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def s29_rule_scope(field_name, conditional_required, learned_rule):
    if learned_rule:
        return "category_brand"
    if conditional_required:
        return "payload_conditional"
    return "category"


def s29_build_profile(inspection_result):
    inspection = inspection_result.get("inspection") or {}
    product = inspection_result.get("product") or {}
    category_result = inspection_result.get("category") or {}
    category_data = category_result.get("data") or {}

    requirements = inspection.get("requirements") or []
    knowledge_rules = []

    for item in requirements:
        field_name = str(item.get("field") or "").upper()
        knowledge_rules.append({
            "rule_key": (
                f"REQUIRE_{field_name}"
                if item.get("required")
                else f"OPTIONAL_{field_name}"
            ),
            "field_name": field_name,
            "required": bool(item.get("required")),
            "conditional": bool(item.get("conditional_required")),
            "location": item.get("location"),
            "accepted_format": item.get("accepted_format"),
            "accepted_values": item.get("accepted_values") or [],
            "outcome": "block_when_missing" if item.get("required") else "informational",
            "explanation": (
                f"{field_name} é exigido pelo Mercado Livre para este contexto."
                if item.get("required")
                else f"{field_name} é opcional para este contexto."
            ),
            "source_endpoint": item.get("source"),
            "evidence": item,
            "confidence": 100,
        })

    learned_rules = (
        ((inspection_result.get("inspection") or {}).get("learned_rules"))
        or []
    )

    gtin_rule = next(
        (
            item for item in knowledge_rules
            if item.get("field_name") == "GTIN"
        ),
        None,
    )
    empty_rule = next(
        (
            item for item in knowledge_rules
            if item.get("field_name") == "EMPTY_GTIN_REASON"
        ),
        None,
    )

    profile = {
        "category_id": inspection.get("category_id"),
        "category_name": inspection.get("category_name"),
        "domain_id": inspection.get("domain_id") or category_data.get("domain_id"),
        "brand": product.get("brand"),
        "listing_type_id": inspection.get("listing_type_id"),
        "can_publish": inspection.get("can_publish"),
        "current_payload_attribute_ids": inspection.get("current_payload_attribute_ids") or [],
        "conditional_required_ids": inspection.get("conditional_required_ids") or [],
        "missing_required_ids": inspection.get("missing_required_ids") or [],
        "unknown_sent_ids": inspection.get("unknown_sent_ids") or [],
        "gtin_policy": {
            "gtin_required": bool(gtin_rule and gtin_rule.get("required")),
            "gtin_conditional": bool(gtin_rule and gtin_rule.get("conditional")),
            "gtin_location": gtin_rule.get("location") if gtin_rule else None,
            "empty_gtin_reason_available": bool(empty_rule),
            "empty_gtin_reason_required": bool(empty_rule and empty_rule.get("required")),
            "empty_gtin_reason_conditional": bool(empty_rule and empty_rule.get("conditional")),
            "empty_gtin_reason_values": (
                empty_rule.get("accepted_values") if empty_rule else []
            ),
            "empty_gtin_reason_substitutes_gtin": bool(
                empty_rule
                and empty_rule.get("required")
                and not (gtin_rule and gtin_rule.get("required"))
            ),
        },
        "rules": knowledge_rules,
        "official_sources": sorted(set(
            str(item.get("source_endpoint") or "")
            for item in knowledge_rules
            if item.get("source_endpoint")
        )),
    }

    profile["fingerprint"] = s29_hash({
        "category_id": profile.get("category_id"),
        "brand": profile.get("brand"),
        "domain_id": profile.get("domain_id"),
        "listing_type_id": profile.get("listing_type_id"),
        "rules": [
            {
                "field": item.get("field_name"),
                "required": item.get("required"),
                "conditional": item.get("conditional"),
                "location": item.get("location"),
                "accepted_format": item.get("accepted_format"),
            }
            for item in knowledge_rules
        ],
    })

    return profile


async def s29_save_profile(inspection_result):
    profile = s29_build_profile(inspection_result)
    product = inspection_result.get("product") or {}

    category_id = str(profile.get("category_id") or "")
    brand = str(product.get("brand") or "").strip()
    domain_id = str(profile.get("domain_id") or "").strip()
    fingerprint = profile.get("fingerprint")

    query = (
        "select=*&category_id=eq." + quote(category_id, safe="-_")
        + "&fingerprint=eq." + quote(str(fingerprint), safe="")
        + ("&brand=eq." + quote(brand, safe="-_ ") if brand else "&brand=is.null")
        + ("&domain_id=eq." + quote(domain_id, safe="-_") if domain_id else "&domain_id=is.null")
        + "&limit=1"
    )

    existing_result = await store.select("ml_knowledge_profiles", query)
    existing_rows = existing_result.get("data") or []
    existing = existing_rows[0] if existing_rows else None

    payload = {
        "company_id": DEFAULT_COMPANY_ID,
        "category_id": category_id,
        "brand": brand or None,
        "domain_id": domain_id or None,
        "fingerprint": fingerprint,
        "status": "active",
        "confidence": 100,
        "profile": profile,
        "official_sources": profile.get("official_sources") or [],
        "last_seen_at": __import__("datetime").datetime.utcnow().isoformat(),
    }

    if existing:
        profile_id = existing.get("id")
        payload["evidence_count"] = int(existing.get("evidence_count") or 0) + 1
        saved = await store.update(
            "ml_knowledge_profiles",
            "id=eq." + quote(str(profile_id), safe="-"),
            payload,
        )
    else:
        payload["evidence_count"] = 1
        payload["first_seen_at"] = __import__("datetime").datetime.utcnow().isoformat()
        saved = await store.insert("ml_knowledge_profiles", payload)
        rows = saved.get("data") or []
        if isinstance(rows, dict):
            rows = [rows]
        profile_id = (rows[0] if rows else {}).get("id")

    if not saved.get("success"):
        return {
            "success": False,
            "profile_id": profile_id if 'profile_id' in locals() else None,
            "error": saved.get("error") or saved.get("raw"),
            "profile": profile,
        }

    if profile_id:
        await store.delete(
            "ml_knowledge_rules",
            "profile_id=eq." + quote(str(profile_id), safe="-"),
        )

        for rule in profile.get("rules") or []:
            await store.insert("ml_knowledge_rules", {
                "profile_id": profile_id,
                "rule_key": rule.get("rule_key"),
                "field_name": rule.get("field_name"),
                "rule_scope": s29_rule_scope(
                    rule.get("field_name"),
                    rule.get("conditional"),
                    False,
                ),
                "required": bool(rule.get("required")),
                "conditional": bool(rule.get("conditional")),
                "location": rule.get("location"),
                "accepted_format": rule.get("accepted_format"),
                "accepted_values": rule.get("accepted_values") or [],
                "outcome": rule.get("outcome"),
                "explanation": rule.get("explanation"),
                "source_endpoint": rule.get("source_endpoint"),
                "evidence": rule.get("evidence") or {},
                "confidence": rule.get("confidence") or 100,
            })

    return {
        "success": True,
        "profile_id": profile_id,
        "profile": profile,
    }


async def s29_knowledge_for_listing(listing_id):
    inspection_result = await s28_inspect_listing(listing_id)
    if not inspection_result.get("success"):
        return inspection_result

    saved = await s29_save_profile(inspection_result)
    profile = saved.get("profile") or {}

    missing = profile.get("missing_required_ids") or []
    unknown = profile.get("unknown_sent_ids") or []

    recommendations = []

    for field_name in missing:
        recommendations.append({
            "action": "provide_required_field",
            "field_name": field_name,
            "message": f"Informe {field_name} antes de publicar.",
        })

    if profile.get("gtin_policy", {}).get("gtin_required"):
        recommendations.append({
            "action": "provide_real_gtin",
            "field_name": "GTIN",
            "message": (
                "O Mercado Livre exige GTIN para este contexto. "
                "Use o código real recebido do fornecedor/fabricante."
            ),
        })

    if (
        profile.get("gtin_policy", {}).get("empty_gtin_reason_available")
        and profile.get("gtin_policy", {}).get("gtin_required")
    ):
        recommendations.append({
            "action": "do_not_treat_empty_gtin_as_substitute",
            "field_name": "EMPTY_GTIN_REASON",
            "message": (
                "EMPTY_GTIN_REASON existe na categoria, mas não substitui "
                "o GTIN nesta validação condicional."
            ),
        })

    return {
        "success": True,
        "version": APP_VERSION,
        "profile_id": saved.get("profile_id"),
        "saved": saved.get("success"),
        "save_error": saved.get("error"),
        "profile": profile,
        "recommendations": recommendations,
        "inspection": inspection_result,
    }


@app.get("/api/marketplace-knowledge/listing/{listing_id}")
async def marketplace_knowledge_api(listing_id: str):
    result = await s29_knowledge_for_listing(listing_id)
    if not result.get("success"):
        return JSONResponse(
            status_code=int(result.get("status_code") or 400),
            content=result,
        )
    return result


@app.get("/marketplace-knowledge/listing/{listing_id}", response_class=HTMLResponse)
async def marketplace_knowledge_page(listing_id: str):
    result = await s29_knowledge_for_listing(listing_id)
    if not result.get("success"):
        return HTMLResponse(
            shell(
                "Marketplace Knowledge Engine",
                f"<div class='card'><h2>Erro</h2><p>{s19e(result.get('error'))}</p></div>",
            ),
            status_code=int(result.get("status_code") or 400),
        )

    profile = result.get("profile") or {}
    gtin = profile.get("gtin_policy") or {}
    recommendations = result.get("recommendations") or []

    recommendation_html = "".join(
        f"<li><b>{s19e(item.get('field_name') or item.get('action'))}</b>: "
        f"{s19e(item.get('message'))}</li>"
        for item in recommendations
    ) or "<li>Nenhuma recomendação.</li>"

    rules_rows = ""
    for item in profile.get("rules") or []:
        if not item.get("required") and not item.get("conditional"):
            continue

        rules_rows += f"""
<tr>
<td>{s19e(item.get('field_name'))}</td>
<td>{'SIM' if item.get('required') else 'NÃO'}</td>
<td>{'SIM' if item.get('conditional') else 'NÃO'}</td>
<td>{s19e(item.get('location'))}</td>
<td>{s19e(item.get('accepted_format'))}</td>
<td>{s19e(item.get('source_endpoint'))}</td>
</tr>
"""

    content = f"""
<div class='grid'>
  <div class='metric'><span>Status</span><strong>{'LIBERADO' if profile.get('can_publish') else 'BLOQUEADO'}</strong></div>
  <div class='metric'><span>Categoria</span><strong>{s19e(profile.get('category_id'))}</strong></div>
  <div class='metric'><span>Marca</span><strong>{s19e(profile.get('brand') or '-')}</strong></div>
  <div class='metric'><span>Perfil</span><strong>{s19e((result.get('profile_id') or '')[:8])}</strong></div>
</div>

<div class='card'>
<h2>Política de GTIN descoberta</h2>
<p><b>GTIN obrigatório:</b> {'SIM' if gtin.get('gtin_required') else 'NÃO'}</p>
<p><b>GTIN condicional:</b> {'SIM' if gtin.get('gtin_conditional') else 'NÃO'}</p>
<p><b>Local:</b> {s19e(gtin.get('gtin_location') or '-')}</p>
<p><b>EMPTY_GTIN_REASON disponível:</b> {'SIM' if gtin.get('empty_gtin_reason_available') else 'NÃO'}</p>
<p><b>Substitui GTIN neste contexto:</b> {'SIM' if gtin.get('empty_gtin_reason_substitutes_gtin') else 'NÃO'}</p>
</div>

<div class='card'>
<h2>Recomendações comprovadas</h2>
<ul>{recommendation_html}</ul>
</div>

<div class='card'>
<h2>Regras oficiais consolidadas</h2>
<table>
<thead>
<tr>
<th>Campo</th>
<th>Obrigatório</th>
<th>Condicional</th>
<th>Local</th>
<th>Formato</th>
<th>Fonte oficial</th>
</tr>
</thead>
<tbody>{rules_rows}</tbody>
</table>
</div>

<div class='card'>
<h2>Fontes oficiais consultadas</h2>
<p>{s19e(', '.join(profile.get('official_sources') or []))}</p>
<p><b>Snapshot salvo:</b> {'SIM' if result.get('saved') else 'NÃO'}</p>
<p><b>Erro ao salvar:</b> {s19e(result.get('save_error') or '-')}</p>
</div>

<div class='card'>
<a class='btn' href='/marketplace-inspector/listing/{listing_id}'>Marketplace Inspector</a>
<a class='btn' href='/api/marketplace-knowledge/listing/{listing_id}'>Ver JSON técnico</a>
<a class='btn' href='/product-master/{result.get("inspection", {}).get("listing", {}).get("product_id")}/listing'>Voltar ao anúncio</a>
</div>
"""
    return HTMLResponse(shell("Marketplace Knowledge Engine", content))


# ==========================================================
# SPRINT 30 - PUBLICATION READINESS PIPELINE
# Integra importação, requisitos oficiais e bloqueio pré-publicação.
# ==========================================================

def s30_value_present(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def s30_product_field_value(product, field_name):
    field_name = str(field_name or "").upper()

    mapping = {
        "BRAND": product.get("brand"),
        "MODEL": product.get("model") or product.get("name"),
        "GTIN": product.get("ean") or product.get("gtin"),
        "SELLER_SKU": product.get("sku"),
        "MPN": product.get("mpn") or product.get("manufacturer_part_number"),
        "WEIGHT": product.get("weight"),
        "HEIGHT": product.get("height"),
        "WIDTH": product.get("width"),
        "LENGTH": product.get("length"),
    }

    return mapping.get(field_name)


async def s30_attribute_values(product_id, category_id):
    try:
        return await s21_product_values(product_id, category_id)
    except Exception:
        return {}


async def s30_build_readiness(listing_id):
    listing = await s19_get_listing(listing_id)
    if not listing:
        return {
            "success": False,
            "status_code": 404,
            "error": "Anúncio não encontrado.",
        }

    context = await s19_product_context(listing.get("product_id"))
    if not context:
        return {
            "success": False,
            "status_code": 404,
            "error": "Produto não encontrado.",
        }

    product = context.get("product") or {}
    category_id = listing.get("category_id")

    # Antes de calcular prontidão, tenta localizar GTIN e completar atributos automaticamente.
    try:
        discovery = await s33_discover_for_listing(listing_id)
        if discovery.get("status") == "found":
            context = await s19_product_context(listing.get("product_id"))
            product = context.get("product") or product
    except Exception:
        pass

    inspection_result = await s28_inspect_listing(listing_id)
    if not inspection_result.get("success"):
        return inspection_result

    inspection = inspection_result.get("inspection") or {}
    requirements = inspection.get("requirements") or []
    values = await s30_attribute_values(product.get("id"), category_id)

    required_fields = []
    completed_fields = []
    missing_fields = []
    invalid_fields = []
    source_map = {}

    for requirement in requirements:
        field_name = str(requirement.get("field") or "").upper()
        if not requirement.get("required"):
            continue

        required_fields.append(field_name)

        attribute_row = values.get(field_name) or values.get(field_name.lower()) or {}
        value = (
            attribute_row.get("value_name")
            or attribute_row.get("value_id")
            or s30_product_field_value(product, field_name)
        )

        source = "manual"
        if attribute_row:
            source = attribute_row.get("source") or "product_marketplace_attributes"
        elif s30_product_field_value(product, field_name) is not None:
            source = "product_master"

        source_map[field_name] = {
            "source": source,
            "value": value,
            "location": requirement.get("location"),
            "accepted_format": requirement.get("accepted_format"),
            "source_endpoint": requirement.get("source"),
        }

        if not s30_value_present(value):
            missing_fields.append({
                "field": field_name,
                "name": requirement.get("name"),
                "location": requirement.get("location"),
                "accepted_format": requirement.get("accepted_format"),
                "accepted_values": requirement.get("accepted_values") or [],
                "source_endpoint": requirement.get("source"),
            })
            continue

        if field_name == "GTIN" and not s212_valid_gtin(value):
            invalid_fields.append({
                "field": "GTIN",
                "value": value,
                "message": "GTIN inválido. Use um código real de 8, 12, 13 ou 14 dígitos.",
                "source_endpoint": requirement.get("source"),
            })
            continue

        completed_fields.append(field_name)

    payload_preview = inspection_result.get("payload_preview") or {}

    # Recalcula e roteia GTIN/EMPTY_GTIN_REASON conforme a estrutura do anúncio.
    gtin_value = s30_product_field_value(product, "GTIN")
    if gtin_value and s212_valid_gtin(gtin_value):
        payload_preview.setdefault("attributes", [])
        payload_preview["attributes"] = s331_remove_ids(
            payload_preview.get("attributes") or [],
            {"GTIN", "EMPTY_GTIN_REASON"}
        )
        payload_preview["attributes"].append({
            "id": "GTIN",
            "value_name": str(gtin_value),
        })

    routed = await s331_apply_identifier_routing(
        context,
        listing,
        payload_preview,
    )
    payload_preview = routed.get("payload") or payload_preview

    total = max(1, len(required_fields))
    score = int(round((len(completed_fields) / total) * 100))
    ready = not missing_fields and not invalid_fields

    readiness = {
        "success": True,
        "version": APP_VERSION,
        "product_id": product.get("id"),
        "listing_id": listing.get("id"),
        "category_id": category_id,
        "status": "ready" if ready else "blocked",
        "readiness_score": score,
        "required_fields": required_fields,
        "completed_fields": completed_fields,
        "missing_fields": missing_fields,
        "invalid_fields": invalid_fields,
        "source_map": source_map,
        "payload_preview": payload_preview,
        "official_requirements": inspection,
    }

    query = (
        "select=*&product_id=eq." + quote(str(product.get("id")), safe="-")
        + "&category_id=eq." + quote(str(category_id), safe="-_")
        + "&limit=1"
    )
    existing_result = await store.select("ml_publication_readiness", query)
    rows = existing_result.get("data") or []
    existing = rows[0] if rows else None

    payload = {
        "company_id": DEFAULT_COMPANY_ID,
        "product_id": product.get("id"),
        "listing_id": listing.get("id"),
        "category_id": category_id,
        "status": readiness["status"],
        "readiness_score": score,
        "required_fields": required_fields,
        "completed_fields": completed_fields,
        "missing_fields": missing_fields,
        "invalid_fields": invalid_fields,
        "source_map": source_map,
        "payload_preview": payload_preview,
        "official_requirements": inspection,
        "last_checked_at": __import__("datetime").datetime.utcnow().isoformat(),
    }

    if existing:
        saved = await store.update(
            "ml_publication_readiness",
            "id=eq." + quote(str(existing.get("id")), safe="-"),
            payload,
        )
    else:
        saved = await store.insert("ml_publication_readiness", payload)

    readiness["saved"] = bool(saved.get("success"))
    readiness["save_error"] = saved.get("error") if not saved.get("success") else None

    return readiness


@app.get("/api/publication-readiness/listing/{listing_id}")
async def publication_readiness_api(listing_id: str):
    result = await s30_build_readiness(listing_id)
    if not result.get("success"):
        return JSONResponse(
            status_code=int(result.get("status_code") or 400),
            content=result,
        )
    return result


@app.get("/publication-readiness/listing/{listing_id}", response_class=HTMLResponse)
async def publication_readiness_page(listing_id: str):
    result = await s30_build_readiness(listing_id)
    if not result.get("success"):
        return HTMLResponse(
            shell(
                "Prontidão para Publicação",
                f"<div class='card'><h2>Erro</h2><p>{s19e(result.get('error'))}</p></div>",
            ),
            status_code=int(result.get("status_code") or 400),
        )

    missing_html = "".join(
        f"<tr><td>{s19e(item.get('field'))}</td>"
        f"<td>{s19e(item.get('name'))}</td>"
        f"<td>{s19e(item.get('location'))}</td>"
        f"<td>{s19e(item.get('accepted_format'))}</td>"
        f"<td>{s19e(item.get('source_endpoint'))}</td></tr>"
        for item in result.get("missing_fields") or []
    ) or "<tr><td colspan='5'>Nenhum campo obrigatório faltando.</td></tr>"

    invalid_html = "".join(
        f"<li><b>{s19e(item.get('field'))}</b>: {s19e(item.get('message'))}</li>"
        for item in result.get("invalid_fields") or []
    ) or "<li>Nenhum campo inválido.</li>"

    source_rows = "".join(
        f"<tr><td>{s19e(field)}</td>"
        f"<td>{s19e(info.get('source'))}</td>"
        f"<td>{s19e(info.get('value'))}</td>"
        f"<td>{s19e(info.get('location'))}</td></tr>"
        for field, info in (result.get("source_map") or {}).items()
    )

    content = f"""
<div class='grid'>
  <div class='metric'><span>Status</span><strong>{'PRONTO' if result.get('status') == 'ready' else 'BLOQUEADO'}</strong></div>
  <div class='metric'><span>Score</span><strong>{result.get('readiness_score')}%</strong></div>
  <div class='metric'><span>Obrigatórios</span><strong>{len(result.get('required_fields') or [])}</strong></div>
  <div class='metric'><span>Faltando</span><strong>{len(result.get('missing_fields') or [])}</strong></div>
</div>

<div class='card'>
<h2>Campos obrigatórios que ainda faltam</h2>
<table>
<thead>
<tr>
<th>Campo</th>
<th>Nome</th>
<th>Local</th>
<th>Formato aceito</th>
<th>Fonte oficial</th>
</tr>
</thead>
<tbody>{missing_html}</tbody>
</table>
</div>

<div class='card'>
<h2>Campos inválidos</h2>
<ul>{invalid_html}</ul>
</div>

<div class='card'>
<h2>Origem dos dados preenchidos</h2>
<table>
<thead><tr><th>Campo</th><th>Origem</th><th>Valor</th><th>Local</th></tr></thead>
<tbody>{source_rows}</tbody>
</table>
</div>

<div class='card'>
<h2>Payload preparado</h2>
<pre>{s19e(json.dumps(result.get('payload_preview') or {}, ensure_ascii=False, indent=2))}</pre>
</div>

<div class='card'>
<a class='btn' href='/marketplace-inspector/listing/{listing_id}'>Marketplace Inspector</a>
<a class='btn' href='/api/publication-readiness/listing/{listing_id}'>Ver JSON técnico</a>
<a class='btn' href='/product-master/{result.get("product_id")}/listing'>Voltar ao anúncio</a>
</div>
"""
    return HTMLResponse(shell("Prontidão para Publicação", content))


@app.post("/api/publication-readiness/listing/{listing_id}/publish")
async def publication_readiness_publish(listing_id: str, request: Request):
    readiness = await s30_build_readiness(listing_id)

    if not readiness.get("success"):
        return JSONResponse(
            status_code=int(readiness.get("status_code") or 400),
            content=readiness,
        )

    if readiness.get("status") != "ready":
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": "Produto ainda não está pronto para publicação.",
                "readiness": readiness,
            },
        )

    listing = await s19_get_listing(listing_id)
    context = await s19_product_context(listing.get("product_id"))
    payload = readiness.get("payload_preview") or {}
    routed = await s331_apply_identifier_routing(context, listing, payload)
    payload = routed.get("payload") or payload

    result = await ml_request("/items", method="POST", payload=payload)

    if not result.get("success"):
        try:
            await s25_record_error(context, listing, result, payload)
        except Exception:
            pass

        return JSONResponse(
            status_code=int(result.get("status_code") or 400),
            content={
                "success": False,
                "error": "Mercado Livre recusou o payload preparado.",
                "result": result,
                "payload_sent": payload,
            },
        )

    item = result.get("data") or {}

    await store.update(
        "listings",
        "id=eq." + quote(str(listing_id), safe="-"),
        {
            "external_id": item.get("id"),
            "permalink": item.get("permalink"),
            "item_url": item.get("permalink"),
            "status": item.get("status") or "active",
            "validation_status": "published",
            "last_error": None,
            "payload": payload,
            "published_at": __import__("datetime").datetime.utcnow().isoformat(),
            "last_synced_at": __import__("datetime").datetime.utcnow().isoformat(),
        },
    )

    return {
        "success": True,
        "message": "Produto publicado com sucesso.",
        "item": item,
        "payload_sent": payload,
    }


# ==========================================================
# SPRINT 31 - GTIN DISCOVERY ENGINE
# Descobre GTIN automaticamente antes da publicação.
# ==========================================================

def s31_digits(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def s31_gtin_type(value):
    digits = s31_digits(value)
    return {
        8: "GTIN-8",
        12: "UPC-A",
        13: "EAN-13",
        14: "GTIN-14",
    }.get(len(digits), "UNKNOWN")


def s31_candidate_keys():
    return {
        "gtin", "ean", "ean13", "ean_13", "barcode", "bar_code",
        "codigo_barras", "codigo_de_barras", "codigobarras",
        "codigo_universal", "upc", "isbn", "product_identifier",
        "global_trade_item_number", "gtin13", "gtin_13",
    }


def s31_extract_candidates(value, path="root", results=None):
    if results is None:
        results = []

    if isinstance(value, dict):
        for key, item in value.items():
            key_norm = str(key).strip().lower()
            new_path = f"{path}.{key}"
            if key_norm in s31_candidate_keys():
                candidate = s31_digits(item)
                if candidate:
                    results.append({
                        "value": candidate,
                        "path": new_path,
                        "key": key_norm,
                    })
            s31_extract_candidates(item, new_path, results)

    elif isinstance(value, list):
        for index, item in enumerate(value):
            s31_extract_candidates(item, f"{path}[{index}]", results)

    return results


def s31_unique_candidates(candidates):
    output = []
    seen = set()
    for item in candidates or []:
        value = s31_digits(item.get("value"))
        if not value or value in seen:
            continue
        seen.add(value)
        output.append({
            **item,
            "value": value,
            "valid": s212_valid_gtin(value),
            "gtin_type": s31_gtin_type(value),
        })
    return output


async def s31_supplier_raw_payload(product):
    possible_fields = [
        "raw_data",
        "raw_payload",
        "supplier_payload",
        "source_payload",
        "metadata",
        "extra_data",
        "import_data",
    ]

    for field_name in possible_fields:
        value = product.get(field_name)
        if value:
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    return parsed
                except Exception:
                    continue
            if isinstance(value, (dict, list)):
                return value

    # Fallback: procura em tabelas comuns de importação, sem quebrar se não existirem.
    product_id = product.get("id")
    fallback_tables = [
        ("supplier_products", f"select=*&product_id=eq.{quote(str(product_id), safe='-')}&limit=1"),
        ("import_items", f"select=*&product_id=eq.{quote(str(product_id), safe='-')}&limit=1"),
        ("supplier_import_items", f"select=*&product_id=eq.{quote(str(product_id), safe='-')}&limit=1"),
    ]

    for table_name, query in fallback_tables:
        try:
            result = await store.select(table_name, query)
            rows = result.get("data") or []
            if rows:
                return rows[0]
        except Exception:
            pass

    return {}


async def s31_history_record(product_id, listing_id, provider, query_data, result_data, found, gtin=None, confidence=0):
    try:
        return await store.insert("gtin_lookup_history", {
            "company_id": DEFAULT_COMPANY_ID,
            "product_id": product_id,
            "listing_id": listing_id,
            "provider": provider,
            "query_data": query_data or {},
            "result_data": result_data or {},
            "found": bool(found),
            "gtin": gtin,
            "confidence": confidence,
        })
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def s31_save_gtin(product, gtin, source, confidence, source_payload=None):
    gtin = s31_digits(gtin)
    if not s212_valid_gtin(gtin):
        return {
            "success": False,
            "error": "GTIN inválido.",
            "gtin": gtin,
        }

    payload = {
        "company_id": DEFAULT_COMPANY_ID,
        "product_id": product.get("id"),
        "brand": product.get("brand"),
        "model": product.get("model") or product.get("name"),
        "mpn": product.get("mpn") or product.get("manufacturer_part_number"),
        "sku": product.get("sku"),
        "gtin": gtin,
        "gtin_type": s31_gtin_type(gtin),
        "source": source,
        "confidence": confidence,
        "source_payload": source_payload or {},
        "verified": confidence >= 95,
    }

    query = (
        "select=*&product_id=eq."
        + quote(str(product.get("id")), safe="-")
        + "&gtin=eq."
        + quote(gtin, safe="")
        + "&limit=1"
    )

    existing_result = await store.select("gtin_catalog", query)
    rows = existing_result.get("data") or []

    if rows:
        saved = await store.update(
            "gtin_catalog",
            "id=eq." + quote(str(rows[0].get("id")), safe="-"),
            payload,
        )
    else:
        saved = await store.insert("gtin_catalog", payload)

    # Atualiza Product Master quando houver coluna compatível.
    product_updates = [
        {"ean": gtin},
        {"gtin": gtin},
    ]
    product_saved = False

    for update_payload in product_updates:
        try:
            result = await store.update(
                "products",
                "id=eq." + quote(str(product.get("id")), safe="-"),
                update_payload,
            )
            if result.get("success"):
                product_saved = True
                break
        except Exception:
            continue

    # Atualiza atributo do marketplace para o payload.
    try:
        values = await s21_product_values(product.get("id"), None)
    except Exception:
        values = {}

    try:
        await store.delete(
            "product_marketplace_attributes",
            "product_id=eq."
            + quote(str(product.get("id")), safe="-")
            + "&marketplace=eq.mercado_livre&attribute_id=eq.GTIN",
        )
        await store.insert("product_marketplace_attributes", {
            "company_id": DEFAULT_COMPANY_ID,
            "product_id": product.get("id"),
            "marketplace": "mercado_livre",
            "category_id": None,
            "attribute_id": "GTIN",
            "value_id": None,
            "value_name": gtin,
            "source": source,
            "confidence": confidence,
            "status": "active",
            "raw_data": {
                "discovery_engine": "sprint31",
                "gtin_type": s31_gtin_type(gtin),
            },
        })
    except Exception:
        pass

    return {
        "success": bool(saved.get("success")),
        "gtin": gtin,
        "source": source,
        "confidence": confidence,
        "product_master_updated": product_saved,
        "catalog_saved": bool(saved.get("success")),
    }


async def s31_lookup_catalog(product):
    product_id = product.get("id")
    brand = str(product.get("brand") or "").strip()
    model = str(product.get("model") or product.get("name") or "").strip()
    mpn = str(product.get("mpn") or product.get("manufacturer_part_number") or "").strip()
    sku = str(product.get("sku") or "").strip()

    queries = []
    if brand and model:
        queries.append(
            "select=*&brand=eq."
            + quote(brand, safe="-_ ")
            + "&model=eq."
            + quote(model, safe="-_ ")
            + "&order=confidence.desc&limit=1"
        )
    if mpn:
        queries.append(
            "select=*&mpn=eq."
            + quote(mpn, safe="-_ ")
            + "&order=confidence.desc&limit=1"
        )
    if sku:
        queries.append(
            "select=*&sku=eq."
            + quote(sku, safe="-_ ")
            + "&order=confidence.desc&limit=1"
        )

    for query in queries:
        result = await store.select("gtin_catalog", query)
        rows = result.get("data") or []
        if rows:
            row = rows[0]
            return {
                "found": True,
                "gtin": row.get("gtin"),
                "confidence": row.get("confidence") or 90,
                "source": "gtin_catalog",
                "record": row,
            }

    return {"found": False}


async def s31_discover_for_listing(listing_id):
    listing = await s19_get_listing(listing_id)
    if not listing:
        return {
            "success": False,
            "status_code": 404,
            "error": "Anúncio não encontrado.",
        }

    context = await s19_product_context(listing.get("product_id"))
    if not context:
        return {
            "success": False,
            "status_code": 404,
            "error": "Produto não encontrado.",
        }

    product = context.get("product") or {}
    product_id = product.get("id")
    attempts = []

    # 1. Product Master
    for field_name in ("ean", "gtin"):
        value = s31_digits(product.get(field_name))
        if value:
            valid = s212_valid_gtin(value)
            attempt = {
                "provider": "product_master",
                "field": field_name,
                "value": value,
                "valid": valid,
                "confidence": 100 if valid else 0,
            }
            attempts.append(attempt)
            await s31_history_record(
                product_id, listing_id, "product_master",
                {"field": field_name},
                attempt, valid, value if valid else None,
                100 if valid else 0,
            )
            if valid:
                saved = await s31_save_gtin(product, value, "product_master", 100, attempt)
                return {
                    "success": True,
                    "status": "found",
                    "gtin": value,
                    "source": "product_master",
                    "confidence": 100,
                    "attempts": attempts,
                    "saved": saved,
                }

    # 2. Payload bruto do fornecedor
    raw_payload = await s31_supplier_raw_payload(product)
    candidates = s31_unique_candidates(
        s31_extract_candidates(raw_payload)
    )

    for candidate in candidates:
        attempts.append({
            "provider": "supplier_raw_payload",
            **candidate,
            "confidence": 100 if candidate.get("valid") else 0,
        })

    valid_supplier = next(
        (item for item in candidates if item.get("valid")),
        None,
    )

    await s31_history_record(
        product_id,
        listing_id,
        "supplier_raw_payload",
        {
            "brand": product.get("brand"),
            "model": product.get("model") or product.get("name"),
            "sku": product.get("sku"),
        },
        {
            "candidates": candidates,
            "payload_present": bool(raw_payload),
        },
        bool(valid_supplier),
        valid_supplier.get("value") if valid_supplier else None,
        100 if valid_supplier else 0,
    )

    if valid_supplier:
        saved = await s31_save_gtin(
            product,
            valid_supplier.get("value"),
            "supplier_raw_payload",
            100,
            {
                "candidate": valid_supplier,
                "raw_payload": raw_payload,
            },
        )
        return {
            "success": True,
            "status": "found",
            "gtin": valid_supplier.get("value"),
            "source": "supplier_raw_payload",
            "confidence": 100,
            "attempts": attempts,
            "saved": saved,
        }

    # 3. Atributos já salvos
    try:
        attrs = await s21_product_values(product_id, listing.get("category_id"))
    except Exception:
        attrs = {}

    gtin_row = attrs.get("GTIN") or attrs.get("gtin") or {}
    attr_value = s31_digits(
        gtin_row.get("value_name") or gtin_row.get("value_id")
    )

    attr_valid = s212_valid_gtin(attr_value) if attr_value else False
    attempts.append({
        "provider": "product_marketplace_attributes",
        "value": attr_value,
        "valid": attr_valid,
        "confidence": 100 if attr_valid else 0,
    })

    await s31_history_record(
        product_id, listing_id,
        "product_marketplace_attributes",
        {},
        {"row": gtin_row, "value": attr_value},
        attr_valid,
        attr_value if attr_valid else None,
        100 if attr_valid else 0,
    )

    if attr_valid:
        saved = await s31_save_gtin(
            product,
            attr_value,
            "product_marketplace_attributes",
            100,
            gtin_row,
        )
        return {
            "success": True,
            "status": "found",
            "gtin": attr_value,
            "source": "product_marketplace_attributes",
            "confidence": 100,
            "attempts": attempts,
            "saved": saved,
        }

    # 4. Catálogo interno aprendido
    catalog_result = await s31_lookup_catalog(product)
    attempts.append({
        "provider": "gtin_catalog",
        **catalog_result,
    })

    await s31_history_record(
        product_id, listing_id,
        "gtin_catalog",
        {
            "brand": product.get("brand"),
            "model": product.get("model") or product.get("name"),
            "mpn": product.get("mpn") or product.get("manufacturer_part_number"),
            "sku": product.get("sku"),
        },
        catalog_result,
        catalog_result.get("found"),
        catalog_result.get("gtin"),
        catalog_result.get("confidence") or 0,
    )

    if catalog_result.get("found") and s212_valid_gtin(catalog_result.get("gtin")):
        saved = await s31_save_gtin(
            product,
            catalog_result.get("gtin"),
            "gtin_catalog",
            catalog_result.get("confidence") or 90,
            catalog_result,
        )
        return {
            "success": True,
            "status": "found",
            "gtin": catalog_result.get("gtin"),
            "source": "gtin_catalog",
            "confidence": catalog_result.get("confidence") or 90,
            "attempts": attempts,
            "saved": saved,
        }

    return {
        "success": True,
        "status": "not_found",
        "gtin": None,
        "source": None,
        "confidence": 0,
        "attempts": attempts,
        "message": (
            "Nenhum GTIN válido foi encontrado nas fontes internas. "
            "O produto permanece bloqueado para publicação."
        ),
    }


@app.get("/api/gtin-discovery/listing/{listing_id}")
async def gtin_discovery_api(listing_id: str):
    result = await s31_discover_for_listing(listing_id)
    if not result.get("success"):
        return JSONResponse(
            status_code=int(result.get("status_code") or 400),
            content=result,
        )
    return result


@app.get("/gtin-discovery/listing/{listing_id}", response_class=HTMLResponse)
async def gtin_discovery_page(listing_id: str):
    result = await s31_discover_for_listing(listing_id)

    if not result.get("success"):
        return HTMLResponse(
            shell(
                "GTIN Discovery Engine",
                f"<div class='card'><h2>Erro</h2><p>{s19e(result.get('error'))}</p></div>",
            ),
            status_code=int(result.get("status_code") or 400),
        )

    attempts_rows = "".join(
        f"<tr>"
        f"<td>{s19e(item.get('provider'))}</td>"
        f"<td>{s19e(item.get('field') or item.get('path') or '-')}</td>"
        f"<td>{s19e(item.get('value') or item.get('gtin') or '-')}</td>"
        f"<td>{'SIM' if item.get('valid') or item.get('found') else 'NÃO'}</td>"
        f"<td>{s19e(item.get('confidence') or 0)}%</td>"
        f"</tr>"
        for item in result.get("attempts") or []
    ) or "<tr><td colspan='5'>Nenhuma tentativa registrada.</td></tr>"

    content = f"""
<div class='grid'>
  <div class='metric'><span>Status</span><strong>{'ENCONTRADO' if result.get('status') == 'found' else 'NÃO ENCONTRADO'}</strong></div>
  <div class='metric'><span>GTIN</span><strong>{s19e(result.get('gtin') or '-')}</strong></div>
  <div class='metric'><span>Origem</span><strong>{s19e(result.get('source') or '-')}</strong></div>
  <div class='metric'><span>Confiança</span><strong>{result.get('confidence') or 0}%</strong></div>
</div>

<div class='card'>
<h2>Fontes verificadas</h2>
<table>
<thead>
<tr>
<th>Fonte</th>
<th>Campo/Caminho</th>
<th>Valor</th>
<th>Válido</th>
<th>Confiança</th>
</tr>
</thead>
<tbody>{attempts_rows}</tbody>
</table>
</div>

<div class='card'>
<h2>Resultado</h2>
<p>{s19e(result.get('message') or 'GTIN localizado e salvo automaticamente.')}</p>
</div>

<div class='card'>
<a class='btn' href='/publication-readiness/listing/{listing_id}'>Atualizar Prontidão</a>
<a class='btn' href='/api/gtin-discovery/listing/{listing_id}'>Ver JSON técnico</a>
<a class='btn' href='/product-master/{(await s19_get_listing(listing_id)).get("product_id")}/listing'>Voltar ao anúncio</a>
</div>
"""
    return HTMLResponse(shell("GTIN Discovery Engine", content))


# ==========================================================
# SPRINT 32 - MARKETPLACE AUTO COMPLETER
# Preenche automaticamente atributos exigidos pelo Mercado Livre.
# ==========================================================

def s32_normalize_key(value):
    import unicodedata
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace(" ", "_").replace("-", "_").replace("/", "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def s32_flatten(value, prefix="", output=None):
    if output is None:
        output = {}

    if isinstance(value, dict):
        for key, item in value.items():
            norm_key = s32_normalize_key(key)
            path = f"{prefix}.{norm_key}" if prefix else norm_key
            if isinstance(item, (dict, list)):
                s32_flatten(item, path, output)
            else:
                output[path] = item
                output.setdefault(norm_key, item)

    elif isinstance(value, list):
        for index, item in enumerate(value):
            s32_flatten(item, f"{prefix}[{index}]", output)

    return output


def s32_transform(value, transform_type, config=None):
    config = config or {}
    transform_type = str(transform_type or "direct").lower()

    if value is None:
        return None

    if transform_type == "digits":
        return "".join(ch for ch in str(value) if ch.isdigit())

    if transform_type == "boolean":
        if isinstance(value, bool):
            return "Sim" if value else "Não"
        text = str(value).strip().lower()
        truthy = {"1", "true", "sim", "yes", "y", "s", "rgb", "ativo", "com"}
        falsy = {"0", "false", "nao", "não", "no", "n", "inativo", "sem"}
        if text in truthy:
            return "Sim"
        if text in falsy:
            return "Não"
        return str(value)

    if transform_type == "number":
        text = str(value).strip().replace(",", ".")
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return match.group(0) if match else None

    return str(value).strip() if isinstance(value, str) else value


async def s32_mapping_rules(supplier, category_id):
    supplier = str(supplier or "").strip().lower()

    query = (
        "select=*&marketplace=eq.mercado_livre"
        + "&active=eq.true"
        + "&order=priority.asc,confidence.desc"
    )
    result = await store.select("ml_attribute_mapping_rules", query)
    rows = result.get("data") or []

    output = []
    for row in rows:
        row_supplier = str(row.get("supplier") or "").strip().lower()
        row_category = str(row.get("category_id") or "").strip()

        if row_supplier and row_supplier != supplier:
            continue
        if row_category and row_category != str(category_id or ""):
            continue

        output.append(row)

    return output


def s32_supplier_name(context):
    supplier = context.get("supplier") or {}
    if isinstance(supplier, dict):
        return (
            supplier.get("name")
            or supplier.get("slug")
            or supplier.get("code")
            or "hayamax"
        )
    return str(supplier or "hayamax")


async def s32_product_source_data(context):
    product = context.get("product") or {}
    raw_payload = await s31_supplier_raw_payload(product)

    combined = {
        "product": product,
        "supplier_raw_payload": raw_payload,
    }

    return s32_flatten(combined)


def s32_find_source_value(flattened, source_field):
    source_field = s32_normalize_key(source_field)

    if source_field in flattened:
        return flattened.get(source_field), source_field

    candidates = [
        key for key in flattened
        if key.endswith("." + source_field)
        or key.endswith("_" + source_field)
    ]

    if candidates:
        candidates.sort(key=len)
        key = candidates[0]
        return flattened.get(key), key

    return None, None


async def s32_existing_attributes(product_id, category_id):
    try:
        return await s21_product_values(product_id, category_id)
    except Exception:
        return {}


async def s32_save_attribute(product_id, category_id, attribute_id, value, source, confidence):
    attribute_id = str(attribute_id or "").upper()

    delete_query = (
        "product_id=eq."
        + quote(str(product_id), safe="-")
        + "&marketplace=eq.mercado_livre"
        + "&category_id=eq."
        + quote(str(category_id), safe="-_")
        + "&attribute_id=eq."
        + quote(attribute_id, safe="_-")
    )

    try:
        await store.delete("product_marketplace_attributes", delete_query)
    except Exception:
        pass

    payload = {
        "company_id": DEFAULT_COMPANY_ID,
        "product_id": product_id,
        "marketplace": "mercado_livre",
        "category_id": category_id,
        "attribute_id": attribute_id,
        "value_id": None,
        "value_name": str(value),
        "source": source,
        "confidence": confidence,
        "status": "active",
        "raw_data": {
            "auto_completer": "sprint32",
        },
    }

    return await store.insert("product_marketplace_attributes", payload)


async def s32_auto_complete_listing(listing_id):
    listing = await s19_get_listing(listing_id)
    if not listing:
        return {
            "success": False,
            "status_code": 404,
            "error": "Anúncio não encontrado.",
        }

    context = await s19_product_context(listing.get("product_id"))
    if not context:
        return {
            "success": False,
            "status_code": 404,
            "error": "Produto não encontrado.",
        }

    product = context.get("product") or {}
    product_id = product.get("id")
    category_id = listing.get("category_id")
    supplier = s32_supplier_name(context).lower()

    inspection_result = await s28_inspect_listing(listing_id)
    if not inspection_result.get("success"):
        return inspection_result

    requirements = (
        inspection_result.get("inspection", {}).get("requirements")
        or []
    )

    required_by_id = {
        str(item.get("field") or "").upper(): item
        for item in requirements
        if item.get("required")
    }

    existing = await s32_existing_attributes(product_id, category_id)
    flattened = await s32_product_source_data(context)
    mappings = await s32_mapping_rules(supplier, category_id)

    applied = []
    completed = []
    missing = []

    for attribute_id, requirement in required_by_id.items():
        existing_row = existing.get(attribute_id) or existing.get(attribute_id.lower()) or {}
        existing_value = existing_row.get("value_name") or existing_row.get("value_id")

        if s30_value_present(existing_value):
            completed.append({
                "field": attribute_id,
                "value": existing_value,
                "source": existing_row.get("source") or "existing_attribute",
                "location": requirement.get("location"),
            })
            continue

        matched = None

        for rule in mappings:
            if str(rule.get("target_attribute_id") or "").upper() != attribute_id:
                continue

            raw_value, source_path = s32_find_source_value(
                flattened,
                rule.get("source_field"),
            )

            transformed = s32_transform(
                raw_value,
                rule.get("transform_type"),
                rule.get("transform_config"),
            )

            if not s30_value_present(transformed):
                continue

            if attribute_id == "GTIN" and not s212_valid_gtin(transformed):
                continue

            matched = {
                "field": attribute_id,
                "value": transformed,
                "source_field": rule.get("source_field"),
                "source_path": source_path,
                "transform_type": rule.get("transform_type"),
                "confidence": rule.get("confidence") or 100,
                "location": requirement.get("location"),
            }
            break

        if matched:
            save_result = await s32_save_attribute(
                product_id,
                category_id,
                attribute_id,
                matched.get("value"),
                "marketplace_auto_completer",
                matched.get("confidence") or 100,
            )

            matched["saved"] = bool(save_result.get("success"))
            applied.append(matched)
            completed.append({
                "field": attribute_id,
                "value": matched.get("value"),
                "source": "marketplace_auto_completer",
                "location": requirement.get("location"),
            })
        else:
            missing.append({
                "field": attribute_id,
                "name": requirement.get("name"),
                "location": requirement.get("location"),
                "accepted_format": requirement.get("accepted_format"),
                "source_endpoint": requirement.get("source"),
            })

    readiness = await s30_build_readiness(listing_id)

    run_payload = {
        "company_id": DEFAULT_COMPANY_ID,
        "product_id": product_id,
        "listing_id": listing_id,
        "category_id": category_id,
        "supplier": supplier,
        "status": "ready" if not missing else "blocked",
        "completed_count": len(completed),
        "missing_count": len(missing),
        "completed_fields": completed,
        "missing_fields": missing,
        "detected_source_fields": flattened,
        "applied_mappings": applied,
        "payload_preview": readiness.get("payload_preview") or {},
    }

    saved_run = await store.insert("ml_auto_completion_runs", run_payload)

    return {
        "success": True,
        "version": APP_VERSION,
        "status": "ready" if not missing else "blocked",
        "supplier": supplier,
        "completed_fields": completed,
        "missing_fields": missing,
        "applied_mappings": applied,
        "readiness": readiness,
        "saved": bool(saved_run.get("success")),
    }


@app.get("/api/marketplace-auto-completer/listing/{listing_id}")
async def marketplace_auto_completer_api(listing_id: str):
    result = await s32_auto_complete_listing(listing_id)

    if not result.get("success"):
        return JSONResponse(
            status_code=int(result.get("status_code") or 400),
            content=result,
        )

    return result


@app.get("/marketplace-auto-completer/listing/{listing_id}", response_class=HTMLResponse)
async def marketplace_auto_completer_page(listing_id: str):
    result = await s32_auto_complete_listing(listing_id)

    if not result.get("success"):
        return HTMLResponse(
            shell(
                "Marketplace Auto Completer",
                f"<div class='card'><h2>Erro</h2><p>{s19e(result.get('error'))}</p></div>",
            ),
            status_code=int(result.get("status_code") or 400),
        )

    applied_rows = "".join(
        f"<tr>"
        f"<td>{s19e(item.get('field'))}</td>"
        f"<td>{s19e(item.get('value'))}</td>"
        f"<td>{s19e(item.get('source_path') or item.get('source_field'))}</td>"
        f"<td>{s19e(item.get('location'))}</td>"
        f"<td>{s19e(item.get('confidence') or 0)}%</td>"
        f"<td>{'SIM' if item.get('saved') else 'NÃO'}</td>"
        f"</tr>"
        for item in result.get("applied_mappings") or []
    ) or "<tr><td colspan='6'>Nenhum novo campo preenchido automaticamente.</td></tr>"

    missing_rows = "".join(
        f"<tr>"
        f"<td>{s19e(item.get('field'))}</td>"
        f"<td>{s19e(item.get('name'))}</td>"
        f"<td>{s19e(item.get('location'))}</td>"
        f"<td>{s19e(item.get('accepted_format'))}</td>"
        f"<td>{s19e(item.get('source_endpoint'))}</td>"
        f"</tr>"
        for item in result.get("missing_fields") or []
    ) or "<tr><td colspan='5'>Nenhum campo obrigatório faltando.</td></tr>"

    content = f"""
<div class='grid'>
  <div class='metric'><span>Status</span><strong>{'PRONTO' if result.get('status') == 'ready' else 'BLOQUEADO'}</strong></div>
  <div class='metric'><span>Fornecedor</span><strong>{s19e(result.get('supplier'))}</strong></div>
  <div class='metric'><span>Preenchidos</span><strong>{len(result.get('completed_fields') or [])}</strong></div>
  <div class='metric'><span>Faltando</span><strong>{len(result.get('missing_fields') or [])}</strong></div>
</div>

<div class='card'>
<h2>Campos preenchidos automaticamente</h2>
<table>
<thead>
<tr>
<th>Campo</th>
<th>Valor</th>
<th>Origem</th>
<th>Local</th>
<th>Confiança</th>
<th>Salvo</th>
</tr>
</thead>
<tbody>{applied_rows}</tbody>
</table>
</div>

<div class='card'>
<h2>Campos obrigatórios que ainda faltam</h2>
<table>
<thead>
<tr>
<th>Campo</th>
<th>Nome</th>
<th>Local</th>
<th>Formato</th>
<th>Fonte oficial</th>
</tr>
</thead>
<tbody>{missing_rows}</tbody>
</table>
</div>

<div class='card'>
<a class='btn' href='/publication-readiness/listing/{listing_id}'>Prontidão para Publicação</a>
<a class='btn' href='/api/marketplace-auto-completer/listing/{listing_id}'>Ver JSON técnico</a>
<a class='btn' href='/product-master/{result.get("readiness", {}).get("product_id")}/listing'>Voltar ao anúncio</a>
</div>
"""

    return HTMLResponse(shell("Marketplace Auto Completer", content))


# ==========================================================
# SPRINT 33 - GTIN INTELLIGENCE ENGINE
# Amplia a descoberta com catálogo do Mercado Livre e score de correspondência.
# ==========================================================

def s33_text(value):
    import unicodedata
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def s33_tokens(value):
    return {
        token for token in s33_text(value).split()
        if len(token) >= 2
    }


def s33_similarity(left, right):
    a = s33_tokens(left)
    b = s33_tokens(right)
    if not a or not b:
        return 0.0
    return round((len(a & b) / len(a | b)) * 100, 2)


def s33_extract_gtins(value, path="root", output=None):
    if output is None:
        output = []

    if isinstance(value, dict):
        for key, item in value.items():
            key_text = s32_normalize_key(key)
            new_path = f"{path}.{key}"

            if key_text in s31_candidate_keys() or key_text in {
                "product_identifier",
                "universal_product_code",
                "identifier",
            }:
                candidate = s31_digits(item)
                if candidate:
                    output.append({
                        "gtin": candidate,
                        "path": new_path,
                        "key": key_text,
                    })

            s33_extract_gtins(item, new_path, output)

    elif isinstance(value, list):
        for index, item in enumerate(value):
            s33_extract_gtins(item, f"{path}[{index}]", output)

    return output


def s33_query_terms(product):
    brand = str(product.get("brand") or "").strip()
    model = str(product.get("model") or "").strip()
    name = str(product.get("name") or "").strip()
    mpn = str(
        product.get("mpn")
        or product.get("manufacturer_part_number")
        or ""
    ).strip()
    sku = str(product.get("sku") or "").strip()

    terms = []

    for value in (
        f"{brand} {model}",
        f"{brand} {name}",
        f"{brand} {mpn}",
        mpn,
        sku,
    ):
        value = " ".join(value.split())
        if value and value not in terms:
            terms.append(value)

    return terms[:5]


async def s33_ml_catalog_search(product, category_id):
    terms = s33_query_terms(product)
    all_candidates = []
    attempts = []

    for term in terms:
        params = {
            "site_id": "MLB",
            "q": term,
            "limit": 20,
        }

        result = await ml_request(
            "/products/search",
            params=params,
        )

        attempts.append({
            "term": term,
            "success": bool(result.get("success")),
            "status_code": result.get("status_code"),
            "error": result.get("error"),
        })

        if not result.get("success"):
            continue

        data = result.get("data") or {}
        rows = (
            data.get("results")
            if isinstance(data, dict)
            else data
        ) or []

        for row in rows:
            if not isinstance(row, dict):
                continue

            title = (
                row.get("name")
                or row.get("title")
                or row.get("short_description")
                or ""
            )
            catalog_product_id = row.get("id") or row.get("catalog_product_id")

            gtins = s33_extract_gtins(row)

            for gtin_item in gtins:
                gtin = s31_digits(gtin_item.get("gtin"))
                valid = s212_valid_gtin(gtin)

                brand_score = s33_similarity(
                    product.get("brand"),
                    row.get("brand") or title,
                )
                model_score = s33_similarity(
                    product.get("model") or product.get("name"),
                    row.get("model") or title,
                )
                title_score = s33_similarity(
                    product.get("name"),
                    title,
                )

                score = round(
                    min(
                        100,
                        brand_score * 0.30
                        + model_score * 0.40
                        + title_score * 0.30
                    ),
                    2,
                )

                all_candidates.append({
                    "provider": "mercado_livre_catalog",
                    "gtin": gtin,
                    "valid": valid,
                    "brand": row.get("brand"),
                    "model": row.get("model"),
                    "title": title,
                    "catalog_product_id": catalog_product_id,
                    "match_score": score,
                    "query_term": term,
                    "path": gtin_item.get("path"),
                    "evidence": row,
                })

    # Remove GTINs duplicados, mantendo o maior score.
    deduped = {}
    for candidate in all_candidates:
        gtin = candidate.get("gtin")
        if not gtin:
            continue
        current = deduped.get(gtin)
        if not current or candidate.get("match_score", 0) > current.get("match_score", 0):
            deduped[gtin] = candidate

    candidates = sorted(
        deduped.values(),
        key=lambda item: (
            bool(item.get("valid")),
            item.get("match_score") or 0,
        ),
        reverse=True,
    )

    selected = next(
        (
            item for item in candidates
            if item.get("valid")
            and float(item.get("match_score") or 0) >= 80
        ),
        None,
    )

    return {
        "success": True,
        "terms": terms,
        "attempts": attempts,
        "candidates": candidates,
        "selected": selected,
    }


async def s33_save_run(product, listing, internal_result, catalog_result):
    selected = catalog_result.get("selected") or {}
    status = (
        "found_internal"
        if internal_result.get("status") == "found"
        else "found_catalog"
        if selected
        else "not_found"
    )

    payload = {
        "company_id": DEFAULT_COMPANY_ID,
        "product_id": product.get("id"),
        "listing_id": listing.get("id"),
        "category_id": listing.get("category_id"),
        "status": status,
        "query_terms": catalog_result.get("terms") or [],
        "internal_result": internal_result or {},
        "ml_catalog_result": {
            "attempts": catalog_result.get("attempts") or [],
        },
        "candidates": catalog_result.get("candidates") or [],
        "selected_candidate": selected,
        "confidence": (
            100
            if internal_result.get("status") == "found"
            else selected.get("match_score") or 0
        ),
    }

    saved = await store.insert("gtin_intelligence_runs", payload)
    rows = saved.get("data") or []
    if isinstance(rows, dict):
        rows = [rows]
    run_id = (rows[0] if rows else {}).get("id")

    if run_id:
        for candidate in catalog_result.get("candidates") or []:
            await store.insert("gtin_intelligence_candidates", {
                "run_id": run_id,
                "provider": candidate.get("provider"),
                "gtin": candidate.get("gtin"),
                "brand": candidate.get("brand"),
                "model": candidate.get("model"),
                "title": candidate.get("title"),
                "catalog_product_id": candidate.get("catalog_product_id"),
                "match_score": candidate.get("match_score") or 0,
                "valid_gtin": bool(candidate.get("valid")),
                "selected": bool(
                    selected
                    and candidate.get("gtin") == selected.get("gtin")
                ),
                "evidence": candidate.get("evidence") or {},
            })

    return {
        "success": bool(saved.get("success")),
        "run_id": run_id,
    }


async def s33_discover_for_listing(listing_id):
    listing = await s19_get_listing(listing_id)
    if not listing:
        return {
            "success": False,
            "status_code": 404,
            "error": "Anúncio não encontrado.",
        }

    context = await s19_product_context(listing.get("product_id"))
    if not context:
        return {
            "success": False,
            "status_code": 404,
            "error": "Produto não encontrado.",
        }

    product = context.get("product") or {}

    # Primeiro, reaproveita toda a inteligência interna da Sprint 31.
    internal_result = await s31_discover_for_listing(listing_id)

    if internal_result.get("status") == "found":
        catalog_result = {
            "success": True,
            "terms": [],
            "attempts": [],
            "candidates": [],
            "selected": None,
        }

        saved_run = await s33_save_run(
            product,
            listing,
            internal_result,
            catalog_result,
        )

        return {
            "success": True,
            "version": APP_VERSION,
            "status": "found",
            "gtin": internal_result.get("gtin"),
            "source": internal_result.get("source"),
            "confidence": internal_result.get("confidence") or 100,
            "internal_result": internal_result,
            "catalog_result": catalog_result,
            "saved_run": saved_run,
        }

    catalog_result = await s33_ml_catalog_search(
        product,
        listing.get("category_id"),
    )
    selected = catalog_result.get("selected")

    saved_run = await s33_save_run(
        product,
        listing,
        internal_result,
        catalog_result,
    )

    if selected:
        save_result = await s31_save_gtin(
            product,
            selected.get("gtin"),
            "mercado_livre_catalog",
            selected.get("match_score") or 80,
            selected,
        )

        return {
            "success": True,
            "version": APP_VERSION,
            "status": "found",
            "gtin": selected.get("gtin"),
            "source": "mercado_livre_catalog",
            "confidence": selected.get("match_score") or 80,
            "internal_result": internal_result,
            "catalog_result": catalog_result,
            "saved": save_result,
            "saved_run": saved_run,
        }

    return {
        "success": True,
        "version": APP_VERSION,
        "status": "not_found",
        "gtin": None,
        "source": None,
        "confidence": 0,
        "message": (
            "Nenhum GTIN confiável foi encontrado nas fontes internas "
            "nem no catálogo consultado do Mercado Livre."
        ),
        "internal_result": internal_result,
        "catalog_result": catalog_result,
        "saved_run": saved_run,
    }


@app.get("/api/gtin-intelligence/listing/{listing_id}")
async def gtin_intelligence_api(listing_id: str):
    result = await s33_discover_for_listing(listing_id)

    if not result.get("success"):
        return JSONResponse(
            status_code=int(result.get("status_code") or 400),
            content=result,
        )

    return result


@app.get("/gtin-intelligence/listing/{listing_id}", response_class=HTMLResponse)
async def gtin_intelligence_page(listing_id: str):
    result = await s33_discover_for_listing(listing_id)

    if not result.get("success"):
        return HTMLResponse(
            shell(
                "GTIN Intelligence Engine",
                f"<div class='card'><h2>Erro</h2><p>{s19e(result.get('error'))}</p></div>",
            ),
            status_code=int(result.get("status_code") or 400),
        )

    catalog = result.get("catalog_result") or {}
    candidates = catalog.get("candidates") or []

    candidate_rows = "".join(
        f"<tr>"
        f"<td>{s19e(item.get('gtin'))}</td>"
        f"<td>{s19e(item.get('title') or '-')}</td>"
        f"<td>{s19e(item.get('catalog_product_id') or '-')}</td>"
        f"<td>{'SIM' if item.get('valid') else 'NÃO'}</td>"
        f"<td>{s19e(item.get('match_score') or 0)}%</td>"
        f"</tr>"
        for item in candidates[:20]
    ) or "<tr><td colspan='5'>Nenhum candidato encontrado.</td></tr>"

    attempts_rows = "".join(
        f"<tr>"
        f"<td>{s19e(item.get('term'))}</td>"
        f"<td>{'SIM' if item.get('success') else 'NÃO'}</td>"
        f"<td>{s19e(item.get('status_code') or '-')}</td>"
        f"<td>{s19e(item.get('error') or '-')}</td>"
        f"</tr>"
        for item in catalog.get("attempts") or []
    ) or "<tr><td colspan='4'>Nenhuma consulta externa executada.</td></tr>"

    content = f"""
<div class='grid'>
  <div class='metric'><span>Status</span><strong>{'ENCONTRADO' if result.get('status') == 'found' else 'NÃO ENCONTRADO'}</strong></div>
  <div class='metric'><span>GTIN</span><strong>{s19e(result.get('gtin') or '-')}</strong></div>
  <div class='metric'><span>Origem</span><strong>{s19e(result.get('source') or '-')}</strong></div>
  <div class='metric'><span>Confiança</span><strong>{s19e(result.get('confidence') or 0)}%</strong></div>
</div>

<div class='card'>
<h2>Consultas ao catálogo do Mercado Livre</h2>
<table>
<thead><tr><th>Termo</th><th>Sucesso</th><th>Status</th><th>Erro</th></tr></thead>
<tbody>{attempts_rows}</tbody>
</table>
</div>

<div class='card'>
<h2>Candidatos encontrados</h2>
<table>
<thead>
<tr>
<th>GTIN</th>
<th>Produto</th>
<th>Catalog Product ID</th>
<th>GTIN válido</th>
<th>Correspondência</th>
</tr>
</thead>
<tbody>{candidate_rows}</tbody>
</table>
</div>

<div class='card'>
<p>{s19e(result.get('message') or 'GTIN encontrado e salvo automaticamente.')}</p>
</div>

<div class='card'>
<a class='btn' href='/publication-readiness/listing/{listing_id}'>Atualizar Prontidão</a>
<a class='btn' href='/api/gtin-intelligence/listing/{listing_id}'>Ver JSON técnico</a>
<a class='btn' href='/product-master/{(await s19_get_listing(listing_id)).get("product_id")}/listing'>Voltar ao anúncio</a>
</div>
"""

    return HTMLResponse(shell("GTIN Intelligence Engine", content))


# ==========================================================
# SPRINT 33.1 - GTIN ROUTING HOTFIX
# Corrige o local do GTIN conforme item sem variações ou com variações.
# ==========================================================

def s331_attr_id(item):
    return str((item or {}).get("id") or "").upper()


def s331_remove_ids(items, ids):
    ids = {str(x).upper() for x in ids}
    return [
        item for item in (items or [])
        if s331_attr_id(item) not in ids
    ]


def s331_has_real_variations(payload):
    variations = payload.get("variations") or []
    if not variations:
        return False

    return any(
        bool(variation.get("attribute_combinations") or [])
        for variation in variations
    )


def s331_find_gtin(attributes):
    for item in attributes or []:
        if s331_attr_id(item) == "GTIN":
            value = item.get("value_name") or item.get("value_id")
            if value:
                return str(value)
    return None


def s331_find_empty_gtin_reason(attributes):
    for item in attributes or []:
        if s331_attr_id(item) == "EMPTY_GTIN_REASON":
            if item.get("value_id"):
                return {"id": "EMPTY_GTIN_REASON", "value_id": item.get("value_id")}
            if item.get("value_name"):
                return {"id": "EMPTY_GTIN_REASON", "value_name": item.get("value_name")}
    return None


def s331_route_product_identifiers(payload, product_values=None):
    product_values = product_values or {}
    item_attributes = list(payload.get("attributes") or [])

    gtin = s331_find_gtin(item_attributes)
    empty_reason = s331_find_empty_gtin_reason(item_attributes)

    if not gtin:
        row = product_values.get("GTIN") or product_values.get("gtin") or {}
        gtin = row.get("value_name") or row.get("value_id")

    if not empty_reason:
        row = (
            product_values.get("EMPTY_GTIN_REASON")
            or product_values.get("empty_gtin_reason")
            or {}
        )
        if row.get("value_id"):
            empty_reason = {"id": "EMPTY_GTIN_REASON", "value_id": row.get("value_id")}
        elif row.get("value_name"):
            empty_reason = {"id": "EMPTY_GTIN_REASON", "value_name": row.get("value_name")}

    item_attributes = s331_remove_ids(
        item_attributes,
        {"GTIN", "EMPTY_GTIN_REASON"}
    )
    payload["attributes"] = item_attributes

    if gtin and s212_valid_gtin(gtin):
        empty_reason = None
    else:
        gtin = None

    has_variations = s331_has_real_variations(payload)

    if has_variations:
        for variation in payload.get("variations") or []:
            variation["attributes"] = s331_remove_ids(
                variation.get("attributes") or [],
                {"GTIN", "EMPTY_GTIN_REASON"}
            )
            variation["attribute_combinations"] = s331_remove_ids(
                variation.get("attribute_combinations") or [],
                {"GTIN", "EMPTY_GTIN_REASON"}
            )

            if gtin:
                variation["attributes"].append({
                    "id": "GTIN",
                    "value_name": str(gtin),
                })

        if empty_reason:
            payload["attributes"].append(empty_reason)

    else:
        payload.pop("variations", None)

        if gtin:
            payload["attributes"].append({
                "id": "GTIN",
                "value_name": str(gtin),
            })
        elif empty_reason:
            payload["attributes"].append(empty_reason)

    return {
        "payload": payload,
        "has_variations": has_variations,
        "gtin": gtin,
        "empty_gtin_reason": empty_reason,
        "routing": (
            "variations[].attributes"
            if has_variations and gtin
            else "item.attributes"
        ),
    }


async def s331_apply_identifier_routing(context, listing, payload):
    product = context.get("product") or {}
    try:
        values = await s21_product_values(
            product.get("id"),
            listing.get("category_id"),
        )
    except Exception:
        values = {}

    return s331_route_product_identifiers(payload, values)


@app.get("/api/identifier-routing/listing/{listing_id}")
async def identifier_routing_api(listing_id: str):
    listing = await s19_get_listing(listing_id)
    if not listing:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Anúncio não encontrado."},
        )

    context = await s19_product_context(listing.get("product_id"))
    payload = s19_build_ml_payload(context, listing, mode="user_product")
    payload["attributes"] = await s21_payload_attributes(
        context["product"].get("id"),
        listing.get("category_id"),
        payload.get("attributes"),
    )

    routed = await s331_apply_identifier_routing(context, listing, payload)

    return {
        "success": True,
        "version": APP_VERSION,
        "listing_id": listing_id,
        "category_id": listing.get("category_id"),
        "routing": routed,
    }
