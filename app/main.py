from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import configure_logging
from app.routers import health, products, supplier, mercado_livre

configure_logging()

app = FastAPI(
    title=settings.APP_NAME,
    description="CommerceHub API - Fornecedor Simulado → Mercado Livre",
    version="0.2.0"
)

app.include_router(health.router, tags=["Sistema"])
app.include_router(supplier.router, prefix="/supplier", tags=["Fornecedor Simulado"])
app.include_router(products.router, prefix="/products", tags=["Produtos"])
app.include_router(mercado_livre.router, prefix="/mercadolivre", tags=["Mercado Livre"])


@app.get("/")
def home():
    return {
        "app": settings.APP_NAME,
        "version": "0.2.0",
        "status": "online",
        "message": "CommerceHub v0.2 rodando com sucesso",
        "flow": "Fornecedor Simulado → CommerceHub → Mercado Livre",
        "endpoints": [
            "/health",
            "/supplier/products",
            "/products",
            "/products/preview-ml",
            "/mercadolivre/status"
        ]
    }
