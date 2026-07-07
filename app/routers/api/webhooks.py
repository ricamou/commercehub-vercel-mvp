from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/mercadolivre")
def mercado_livre_webhook_check():
    return {
        "status": "ok",
        "message": "Webhook Mercado Livre ativo."
    }


@router.post("/mercadolivre")
async def mercado_livre_webhook(request: Request):
    payload = await request.json()

    # Nesta milestone apenas confirmamos o recebimento.
    # Em etapa futura, salvaremos eventos e processaremos pedidos/anúncios/perguntas.
    return {
        "received": True,
        "source": "mercado_livre",
        "payload": payload
    }
