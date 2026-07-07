import os

def clean_env(value: str) -> str:
    if value is None:
        return ""
    value = str(value).strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()
    return value

class Settings:
    APP_NAME = clean_env(os.getenv("APP_NAME", "CommerceHub"))
    APP_ENV = clean_env(os.getenv("APP_ENV", "production"))
    APP_VERSION = clean_env(os.getenv("APP_VERSION", "simple-working-v1"))
    APP_URL = clean_env(os.getenv("APP_URL", "https://commercehub-vercel-mvp.vercel.app"))

    ML_CLIENT_ID = clean_env(os.getenv("ML_CLIENT_ID", ""))
    ML_CLIENT_SECRET = clean_env(os.getenv("ML_CLIENT_SECRET", ""))
    ML_REDIRECT_URI = clean_env(os.getenv("ML_REDIRECT_URI", f"{APP_URL}/mercadolivre/callback"))
    ML_ACCESS_TOKEN = clean_env(os.getenv("ML_ACCESS_TOKEN", ""))
    ML_REFRESH_TOKEN = clean_env(os.getenv("ML_REFRESH_TOKEN", ""))
    ML_TOKEN_EXPIRES_IN = clean_env(os.getenv("ML_TOKEN_EXPIRES_IN", ""))
    ML_USER_ID = clean_env(os.getenv("ML_USER_ID", ""))

    DEFAULT_MARGIN_PERCENT = float(clean_env(os.getenv("DEFAULT_MARGIN_PERCENT", "35")) or 35)
    ML_COMMISSION_PERCENT = float(clean_env(os.getenv("ML_COMMISSION_PERCENT", "16")) or 16)
    FIXED_OPERATIONAL_COST = float(clean_env(os.getenv("FIXED_OPERATIONAL_COST", "6")) or 6)

settings = Settings()
