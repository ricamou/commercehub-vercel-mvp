import os


def clean_env(value: str) -> str:
    if value is None:
        return ""

    value = str(value).strip()

    # Remove aspas comuns quando o valor é colado como string.
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()

    # Remove vírgula final quando vem copiado de JSON/dict.
    value = value.rstrip(",").strip()

    return value


class Settings:
    APP_NAME: str = clean_env(os.getenv("APP_NAME", "CommerceHub"))
    APP_ENV: str = clean_env(os.getenv("APP_ENV", "production"))

    DEFAULT_MARGIN_PERCENT: float = float(clean_env(os.getenv("DEFAULT_MARGIN_PERCENT", "35")) or "35")
    ML_COMMISSION_PERCENT: float = float(clean_env(os.getenv("ML_COMMISSION_PERCENT", "16")) or "16")
    FIXED_OPERATIONAL_COST: float = float(clean_env(os.getenv("FIXED_OPERATIONAL_COST", "6.00")) or "6.00")

    ML_CLIENT_ID: str = clean_env(os.getenv("ML_CLIENT_ID", ""))
    ML_CLIENT_SECRET: str = clean_env(os.getenv("ML_CLIENT_SECRET", ""))
    ML_REDIRECT_URI: str = clean_env(os.getenv("ML_REDIRECT_URI", ""))

    ML_ACCESS_TOKEN: str = clean_env(os.getenv("ML_ACCESS_TOKEN", ""))
    ML_REFRESH_TOKEN: str = clean_env(os.getenv("ML_REFRESH_TOKEN", ""))
    ML_TOKEN_EXPIRES_IN: str = clean_env(os.getenv("ML_TOKEN_EXPIRES_IN", ""))
    ML_USER_ID: str = clean_env(os.getenv("ML_USER_ID", ""))


settings = Settings()
