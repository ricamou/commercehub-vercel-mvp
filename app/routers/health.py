from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "commercehub-api",
        "version": "0.2.0",
        "environment": settings.APP_ENV
    }
