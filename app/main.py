from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import configure_logging
from app.routers.api import health, products, supplier, mercado_livre, webhooks
from app.routers.web import pages

configure_logging()

app = FastAPI(
    title=settings.APP_NAME,
    description="CommerceHub - Fornecedor Simulado → Mercado Livre",
    version="1.0.0-milestone-1"
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(pages.router, tags=["Painel Web"])

app.include_router(health.router, prefix="/api", tags=["API - Sistema"])
app.include_router(supplier.router, prefix="/api/supplier", tags=["API - Fornecedor Simulado"])
app.include_router(products.router, prefix="/api/products", tags=["API - Produtos"])
app.include_router(mercado_livre.router, prefix="/api/mercadolivre", tags=["API - Mercado Livre"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["API - Webhooks"])
