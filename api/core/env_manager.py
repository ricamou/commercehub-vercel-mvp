import os
import re
from urllib.parse import urlparse

FALLBACKS = {
    "SUPABASE_URL": ["NEXT_PUBLIC_SUPABASE_URL"],
    "SUPABASE_SERVICE_ROLE_KEY": ["SUPABASE_KEY"],
    "SUPABASE_ANON_KEY": ["NEXT_PUBLIC_SUPABASE_ANON_KEY"],
}

def clean(value):
    if value is None:
        return ""
    value = str(value).strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()
    return value

def get(name):
    value = clean(os.getenv(name))
    if value:
        return value, name
    for fallback in FALLBACKS.get(name, []):
        value = clean(os.getenv(fallback))
        if value:
            return value, fallback
    return "", ""

def mask(value):
    value = clean(value)
    if not value:
        return {"present": False, "length": 0, "preview": ""}
    return {"present": True, "length": len(value), "preview": (value[:12] + "..." + value[-8:]) if len(value) > 28 else value[:6] + "..."}

def is_placeholder(value):
    low = clean(value).lower()
    return any(x in low for x in ["seu-projeto", "seuprojeto", "projectref", "example", "xxxx", "sua-chave", "your-", "placeholder"])

def jwt_info(value):
    value = clean(value)
    parts = value.split('.') if value else []
    return {"starts_eyj": value.startswith('eyJ'), "parts": len(parts), "length": len(value), "looks_jwt": value.startswith('eyJ') and len(parts)==3 and len(value)>=120}

def analyze_url(value):
    value = clean(value)
    issues=[]
    parsed = urlparse(value) if value else None
    if not value: issues.append('URL ausente.')
    if value and not value.startswith('https://'): issues.append('A URL deve começar com https://')
    if value and not value.endswith('.supabase.co'): issues.append('A URL deve terminar com .supabase.co')
    if is_placeholder(value): issues.append('A URL é placeholder/exemplo.')
    if ' ' in value or '\n' in value or '\r' in value: issues.append('A URL contém espaço ou quebra de linha.')
    host = parsed.hostname if parsed else ''
    project_ref = host.replace('.supabase.co','') if host and host.endswith('.supabase.co') else ''
    if value and not re.match(r'^https://[a-z0-9]{15,30}\.supabase\.co$', value): issues.append('Formato esperado: https://PROJECTREF.supabase.co')
    return {"ok": len(issues)==0, "masked": mask(value), "host": host, "project_ref_preview": (project_ref[:6]+'...') if project_ref else '', "issues": issues}

def analyze_jwt(value, label):
    value = clean(value); info=jwt_info(value); issues=[]
    if not value: issues.append(f'{label} ausente.')
    if value and is_placeholder(value): issues.append(f'{label} parece placeholder/exemplo.')
    if value and not info['starts_eyj']: issues.append(f'{label} normalmente começa com eyJ.')
    if value and info['parts'] != 3: issues.append(f'{label} precisa ter 3 partes separadas por ponto.')
    if value and len(value) < 120: issues.append(f'{label} parece curta demais.')
    if ' ' in value or '\n' in value or '\r' in value: issues.append(f'{label} contém espaço ou quebra de linha.')
    return {"ok": len(issues)==0, "masked": mask(value), "jwt": info, "issues": issues}

def full_env_report():
    supabase_url, supabase_url_source = get('SUPABASE_URL')
    service_role, service_role_source = get('SUPABASE_SERVICE_ROLE_KEY')
    anon_key, anon_key_source = get('SUPABASE_ANON_KEY')
    ml_client_id, ml_client_id_source = get('ML_CLIENT_ID')
    ml_client_secret, ml_client_secret_source = get('ML_CLIENT_SECRET')
    ml_redirect_uri, ml_redirect_uri_source = get('ML_REDIRECT_URI')
    checks={
        'SUPABASE_URL': {'source': supabase_url_source, **analyze_url(supabase_url)},
        'SUPABASE_SERVICE_ROLE_KEY': {'source': service_role_source, **analyze_jwt(service_role,'SUPABASE_SERVICE_ROLE_KEY')},
        'SUPABASE_ANON_KEY': {'source': anon_key_source, **analyze_jwt(anon_key,'SUPABASE_ANON_KEY')},
        'ML_CLIENT_ID': {'source': ml_client_id_source, 'ok': bool(ml_client_id), 'masked': mask(ml_client_id), 'issues': [] if ml_client_id else ['ML_CLIENT_ID ausente.']},
        'ML_CLIENT_SECRET': {'source': ml_client_secret_source, 'ok': bool(ml_client_secret), 'masked': mask(ml_client_secret), 'issues': [] if ml_client_secret else ['ML_CLIENT_SECRET ausente.']},
        'ML_REDIRECT_URI': {'source': ml_redirect_uri_source, 'ok': bool(ml_redirect_uri and ml_redirect_uri.startswith('http')), 'masked': mask(ml_redirect_uri), 'issues': [] if ml_redirect_uri and ml_redirect_uri.startswith('http') else ['ML_REDIRECT_URI ausente ou inválida.']},
    }
    exact=[]
    for n,item in checks.items():
        for issue in item.get('issues',[]): exact.append(f'{n}: {issue}')
    required_ok = all(checks[n]['ok'] for n in ['SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY','SUPABASE_ANON_KEY'])
    return {"production_ready_supabase": required_ok, "checks": checks, "exact_errors": exact, "next_steps": ["Corrigir variáveis em Vercel > Settings > Environment Variables.", "Usar valores reais do Supabase > Project Settings > API.", "Salvar variáveis para Production e Preview.", "Fazer Redeploy obrigatório.", "Testar /api/environment/full e /api/raw/full."]}
