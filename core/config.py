import os

def env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if value is None:
        return ""
    value = str(value).strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()
    return value

APP_URL = env("APP_URL", "https://commercehub-vercel-mvp.vercel.app")

ML_CLIENT_ID = env("ML_CLIENT_ID")
ML_CLIENT_SECRET = env("ML_CLIENT_SECRET")
ML_REDIRECT_URI = env("ML_REDIRECT_URI", f"{APP_URL}/api/mercadolivre/callback")
ML_ACCESS_TOKEN = env("ML_ACCESS_TOKEN")
ML_REFRESH_TOKEN = env("ML_REFRESH_TOKEN")
ML_USER_ID = env("ML_USER_ID")

DEFAULT_MARGIN_PERCENT = float(env("DEFAULT_MARGIN_PERCENT", "35") or 35)
ML_COMMISSION_PERCENT = float(env("ML_COMMISSION_PERCENT", "16") or 16)
FIXED_OPERATIONAL_COST = float(env("FIXED_OPERATIONAL_COST", "6") or 6)