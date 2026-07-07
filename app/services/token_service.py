from app.core.config import settings


class TokenService:
    def get_token_status(self):
        return {
            "access_token_configured": bool(settings.ML_ACCESS_TOKEN),
            "refresh_token_configured": bool(settings.ML_REFRESH_TOKEN),
            "token_expires_in_configured": bool(settings.ML_TOKEN_EXPIRES_IN),
            "user_id_configured": bool(settings.ML_USER_ID),
            "storage_mode": "environment_variables",
            "message": "Nesta milestone os tokens são lidos das variáveis de ambiente da Vercel."
        }
