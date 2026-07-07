import os


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "CommerceHub")
    APP_ENV: str = os.getenv("APP_ENV", "production")

    DEFAULT_MARGIN_PERCENT: float = float(os.getenv("DEFAULT_MARGIN_PERCENT", "35"))
    ML_COMMISSION_PERCENT: float = float(os.getenv("ML_COMMISSION_PERCENT", "16"))
    FIXED_OPERATIONAL_COST: float = float(os.getenv("FIXED_OPERATIONAL_COST", "6.00"))

    ML_CLIENT_ID: str = os.getenv("ML_CLIENT_ID", "")
    ML_CLIENT_SECRET: str = os.getenv("ML_CLIENT_SECRET", "")
    ML_REDIRECT_URI: str = os.getenv("ML_REDIRECT_URI", "")

    ML_ACCESS_TOKEN: str = os.getenv("ML_ACCESS_TOKEN", "")
    ML_REFRESH_TOKEN: str = os.getenv("ML_REFRESH_TOKEN", "")
    ML_TOKEN_EXPIRES_IN: str = os.getenv("ML_TOKEN_EXPIRES_IN", "")
    ML_USER_ID: str = os.getenv("ML_USER_ID", "")


settings = Settings()
