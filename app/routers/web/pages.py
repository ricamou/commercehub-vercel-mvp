from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.connectors.mercado_livre.client import MercadoLivreClient
from app.services.dashboard_service import DashboardService
from app.services.product_service import ProductService
from app.services.supplier_service import SupplierService
from app.services.token_service import TokenService
from app.services.ad_service import AdService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

dashboard_service = DashboardService()
product_service = ProductService()
supplier_service = SupplierService()
ml_client = MercadoLivreClient()
token_service = TokenService()
ad_service = AdService()


@router.get("/")
def index(request: Request):
    return dashboard(request)


@router.get("/dashboard")
def dashboard(request: Request):
    data = dashboard_service.get_dashboard_data()
    return templates.TemplateResponse("dashboard.html", {"request": request, "page_title": "Dashboard", "data": data})


@router.get("/produtos")
def produtos(request: Request):
    products = product_service.list_products_with_sale_price()
    return templates.TemplateResponse("products.html", {"request": request, "page_title": "Produtos", "products": products})


@router.get("/fornecedor")
def fornecedor(request: Request):
    products = supplier_service.list_products()
    return templates.TemplateResponse("supplier.html", {"request": request, "page_title": "Fornecedor Simulado", "products": products})


@router.get("/mercado-livre")
async def mercado_livre(request: Request):
    status = ml_client.status()
    token_status = token_service.get_token_status()
    account = await ml_client.get_me() if status["access_token_configured"] else None

    return templates.TemplateResponse(
        "mercado_livre.html",
        {
            "request": request,
            "page_title": "Mercado Livre",
            "status": status,
            "token_status": token_status,
            "auth_url": ml_client.get_authorization_url(),
            "account": account
        }
    )


@router.get("/mercadolivre/connect")
def mercado_livre_connect():
    auth_url = ml_client.get_authorization_url()
    if not auth_url:
        return RedirectResponse(url="/mercado-livre")
    return RedirectResponse(url=auth_url)


@router.get("/mercadolivre/callback")
async def mercado_livre_callback(request: Request, code: str | None = None, error: str | None = None):
    if error:
        return templates.TemplateResponse(
            "mercado_livre_callback.html",
            {"request": request, "page_title": "Callback Mercado Livre", "success": False, "message": f"Mercado Livre retornou erro: {error}", "token_data": None}
        )

    if not code:
        return templates.TemplateResponse(
            "mercado_livre_callback.html",
            {"request": request, "page_title": "Callback Mercado Livre", "success": False, "message": "Nenhum code foi recebido.", "token_data": None}
        )

    result = await ml_client.exchange_code_for_token(code)

    token_data = result.get("data", {}) if isinstance(result, dict) else {}

    return templates.TemplateResponse(
        "mercado_livre_callback.html",
        {
            "request": request,
            "page_title": "Callback Mercado Livre",
            "success": result["success"],
            "message": "Token recebido. Copie cada campo abaixo para a variável correta na Vercel." if result["success"] else "Falha ao trocar code por token.",
            "token_data": token_data,
            "access_token": token_data.get("access_token", ""),
            "refresh_token": token_data.get("refresh_token", ""),
            "expires_in": token_data.get("expires_in", ""),
            "user_id": token_data.get("user_id", "")
        }
    )


@router.get("/anuncios")
def anuncios(request: Request):
    products = product_service.list_products_with_sale_price()

    enriched_products = []
    for product in products:
        enriched_products.append({
            **product,
            "suggested_search": ad_service.suggest_search_term(product)
        })

    return templates.TemplateResponse(
        "ads.html",
        {
            "request": request,
            "page_title": "Produtos e Anúncios",
            "products": enriched_products
        }
    )
