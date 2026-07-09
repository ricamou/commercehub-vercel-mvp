import os

def env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if value is None:
        return ""
    value = str(value).strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()
    return value

APP_VERSION = "enterprise-v4-sprint2-supabase-httpx"
APP_URL = env("APP_URL", "https://commercehub-vercel-mvp.vercel.app")
SUPABASE_URL = env("SUPABASE_URL") or env("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = env("SUPABASE_SERVICE_ROLE_KEY") or env("SUPABASE_KEY") or env("SUPABASE_ANON_KEY")
ML_CLIENT_ID = env("ML_CLIENT_ID")
ML_CLIENT_SECRET = env("ML_CLIENT_SECRET")
ML_REDIRECT_URI = env("ML_REDIRECT_URI", f"{APP_URL}/mercadolivre/callback")
DEFAULT_COMPANY_ID = "00000000-0000-0000-0000-000000000001"
