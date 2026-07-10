from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import json, uuid, hashlib, hmac, base64, time, csv, io, xml.etree.ElementTree as ET
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

S13_VERSION = "enterprise-v5-sprint18-product-master"
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
<p><b>EAN:</b> {s18_escape(product.get('ean') or '-')}</p>
<p><b>SEO:</b> {s18_escape(product.get('seo_name') or '-')}</p>
<p><b>NCM:</b> {s18_escape(product.get('ncm') or '-')}</p>
<p><b>Dimensões:</b> {s18_escape(product.get('height_cm') or 0)} × {s18_escape(product.get('width_cm') or 0)} × {s18_escape(product.get('length_cm') or 0)} cm</p>
<p><b>Peso:</b> {s18_escape(product.get('weight_kg') or 0)} kg</p>
<p><b>Descrição:</b><br>{s18_escape(product.get('description') or '-')}</p>
<a class='btn' href='/product-master/{product_id}/edit'>Editar</a>
<a class='btn' href='/product-master/{product_id}/images'>Imagens</a>
<a class='btn' href='/product-master/{product_id}/attributes'>Atributos</a>
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

    result = await store.select("product_images", f"select=*&product_id=eq.{quote(product_id, safe='-')}&order=position.asc")
    rows = "".join(
        f"<tr><td><img src='{s18_escape(i.get('url'))}' style='width:70px;height:70px;object-fit:contain'></td><td>{s18_escape(i.get('url'))}</td><td>{s18_escape(i.get('position'))}</td><td>{'Sim' if i.get('is_main') else 'Não'}</td></tr>"
        for i in (result.get("data") or [])
    ) or "<tr><td colspan='4'>Nenhuma imagem.</td></tr>"

    content = f"""
<div class='card'>
<h2>Adicionar imagem — {s18_escape(product.get('sku'))}</h2>
<form method='post' action='/api/product-master/{product_id}/images'>
<label>URL da imagem</label><input name='url' required>
<label>Texto alternativo</label><input name='alt_text'>
<label>Posição</label><input name='position' value='0'>
<label><input type='checkbox' name='is_main' value='true' style='width:auto'> Imagem principal</label><br><br>
<button type='submit'>Adicionar imagem</button>
</form>
</div>
<div class='card'><table><thead><tr><th>Imagem</th><th>URL</th><th>Posição</th><th>Principal</th></tr></thead><tbody>{rows}</tbody></table></div>
"""
    return HTMLResponse(shell("Imagens do Produto", content))


@app.post("/api/product-master/{product_id}/images")
async def product_master_add_image(product_id: str, request: Request):
    product = await s18_get_product(product_id)
    if not product:
        return JSONResponse(status_code=404, content={"success": False, "error": "Produto não encontrado."})

    form = await request.form()
    url = str(form.get("url") or "").strip()
    if not url:
        return JSONResponse(status_code=400, content={"success": False, "error": "URL obrigatória."})

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
