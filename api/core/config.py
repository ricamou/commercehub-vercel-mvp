import os

APP_VERSION = "enterprise-v5-sprint10-core-operation"

def env(name, default=""):
    value = os.getenv(name, default)
    if value is None:
        return ""
    value = str(value).strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()
    return value

def first_env(*names):
    for name in names:
        value = env(name)
        if value:
            return value
    return ""

SUPABASE_URL = first_env("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = first_env("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY")
SUPABASE_ANON_KEY = first_env("SUPABASE_ANON_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY")
SUPABASE_KEY = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY
ML_CLIENT_ID = env("ML_CLIENT_ID")
ML_CLIENT_SECRET = env("ML_CLIENT_SECRET")
ML_REDIRECT_URI = env("ML_REDIRECT_URI")
ML_ACCESS_TOKEN = env("ML_ACCESS_TOKEN")
ML_REFRESH_TOKEN = env("ML_REFRESH_TOKEN")
ML_USER_ID = env("ML_USER_ID")
APP_URL = env("APP_URL", "https://commercehub-vercel-mvp.vercel.app")
DEFAULT_COMPANY_ID = "00000000-0000-0000-0000-000000000001"

def is_placeholder(value):
    low = str(value or '').lower()
    return any(x in low for x in ["seu-projeto", "seuprojeto", "projectref", "example", "xxxx", "sua-chave", "your-", "placeholder"])

def supabase_configured():
    return bool(SUPABASE_URL and SUPABASE_KEY and not is_placeholder(SUPABASE_URL) and not is_placeholder(SUPABASE_KEY))
