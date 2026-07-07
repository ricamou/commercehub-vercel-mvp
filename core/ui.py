def layout(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · CommerceHub</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:#f4f7fb;color:#111827}}
aside{{position:fixed;left:0;top:0;bottom:0;width:230px;background:#0b1220;color:white;padding:22px 16px}}
.logo{{display:flex;gap:10px;align-items:center;margin-bottom:28px}}.logo b{{background:#2563eb;padding:12px;border-radius:10px}}.logo span{{display:block;color:#9ca3af;font-size:12px}}
nav a{{display:block;color:white;text-decoration:none;padding:10px 8px;border-radius:8px;margin:4px 0}}nav a:hover{{background:#172033}}
main{{margin-left:230px;padding:28px}}h1{{font-size:34px;margin:0}}header p{{color:#64748b}}
.grid{{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:16px;margin:22px 0}}.card,.panel{{background:white;border:1px solid #d8dee8;border-radius:16px;box-shadow:0 8px 24px rgba(15,23,42,.05)}}
.card{{padding:22px}}.card span{{display:block;color:#64748b}}.card strong{{font-size:30px;display:block;margin-top:10px}}
.panel{{padding:22px;margin:18px 0}}table{{width:100%;border-collapse:collapse;margin-top:12px}}th,td{{padding:12px;border-bottom:1px solid #e5e7eb;text-align:left}}th{{background:#f8fafc}}
pre{{background:#0b1220;color:white;padding:14px;border-radius:10px;overflow:auto}}code{{background:#eef2ff;padding:3px 6px;border-radius:6px}}.btn{{display:inline-block;background:#2563eb;color:white;text-decoration:none;padding:12px 16px;border-radius:10px;margin:8px 0}}
</style>
</head>
<body>
<aside>
<div class="logo"><b>CH</b><div><strong>CommerceHub</strong><span>v2 Enterprise</span></div></div>
<nav>
<a href="/dashboard">Dashboard</a>
<a href="/mercado-livre">Mercado Livre</a>
<a href="/fornecedores">Fornecedores</a>
<a href="/produtos">Produtos</a>
<a href="/anuncios">Anúncios</a>
<a href="/pedidos">Pedidos</a>
<a href="/relatorios">Relatórios</a>
<a href="/ai">AI Engine</a>
<a href="/usuarios">Usuários</a>
<a href="/database">Database</a>
<a href="/arquitetura">Arquitetura</a>
<a href="/api/health" target="_blank">API Health</a>
</nav>
</aside>
<main>
<header><h1>{title}</h1><p>Fornecedor → CommerceHub → Mercado Livre → Cliente</p></header>
{body}
</main>
</body>
</html>"""