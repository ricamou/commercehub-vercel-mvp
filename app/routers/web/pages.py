from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.connectors.mercado_livre.client import MercadoLivreClient
from app.services.dashboard_service import DashboardService
from app.services.product_service import ProductService
from app.services.supplier_service import SupplierService
from app.services.token_service import TokenService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

dashboard_service = DashboardService()
product_service = ProductService()
supplier_service = SupplierService()
ml_client = MercadoLivreClient()
token_service = TokenService()


@router.get("/")
def index(request: Request):
    return dashboard(request)


@router.get("/dashboard")
def dashboard(request: Request):
    data = dashboard_service.get_dashboard_data()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "page_title": "Dashboard",
            "data": data
        }
    )


@router.get("/produtos")
def produtos(request: Request):
    products = product_service.list_products_with_sale_price()
    return templates.TemplateResponse(
        "products.html",
        {
            "request": request,
            "page_title": "Produtos",
            "products": products
        }
    )


@router.get("/fornecedor")
def fornecedor(request: Request):
    products = supplier_service.list_products()
    return templates.TemplateResponse(
        "supplier.html",
        {
            "request": request,
            "page_title": "Fornecedor Simulado",
            "products": products
        }
    )


@router.get("/mercado-livre")
def mercado_livre(request: Request):
    status = ml_client.status()
    token_status = token_service.get_token_status()

    return templates.TemplateResponse(
        "mercado_livre.html",
        {
            "request": request,
            "page_title": "Mercado Livre",
            "status": status,
            "token_status": token_status,
            "auth_url": ml_client.get_authorization_url()
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
            {
                "request": request,
                "page_title": "Callback Mercado Livre",
                "success": False,
                "message": f"Mercado Livre retornou erro: {error}",
                "token_data": None
            }
        )

    if not code:
        return templates.TemplateResponse(
            "mercado_livre_callback.html",
            {
                "request": request,
                "page_title": "Callback Mercado Livre",
                "success": False,
                "message": "Nenhum code foi recebido.",
                "token_data": None
            }
        )

    result = await ml_client.exchange_code_for_token(code)

    return templates.TemplateResponse(
        "mercado_livre_callback.html",
        {
            "request": request,
            "page_title": "Callback Mercado Livre",
            "success": result["success"],
            "message": "Token recebido. Copie os tokens para as variáveis da Vercel." if result["success"] else "Falha ao trocar code por token.",
            "token_data": result["data"]
        }
    )
