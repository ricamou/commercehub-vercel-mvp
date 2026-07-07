from datetime import datetime
import uuid


def simulate_order():
    return {
        "id": str(uuid.uuid4()),
        "marketplace": "mercado_livre",
        "external_order_id": "MLB-ORDER-TEST-001",
        "status": "paid",
        "total_amount": 89.90,
        "payload": {
            "buyer": {"nickname": "cliente_teste"},
            "items": [{"sku": "SUP-001", "quantity": 1, "price": 89.90}]
        },
        "created_at": datetime.utcnow().isoformat()
    }


def normalize_ml_webhook(payload: dict):
    return {
        "event_type": "mercado_livre_webhook",
        "message": "Webhook Mercado Livre recebido",
        "payload": payload,
        "created_at": datetime.utcnow().isoformat()
    }


def normalize_order_from_payload(marketplace: str, payload: dict):
    return {
        "marketplace": marketplace,
        "external_order_id": str(payload.get("id") or payload.get("order_id") or payload.get("resource") or ""),
        "status": payload.get("status", "received"),
        "total_amount": float(payload.get("total_amount") or payload.get("paid_amount") or 0),
        "payload": payload,
        "created_at": datetime.utcnow().isoformat()
    }


def route_order_to_supplier(order: dict):
    payload = order.get("payload", {}) or {}
    items = payload.get("items") or payload.get("order_items") or []
    routes = []

    for item in items:
        sku = item.get("sku") or item.get("seller_custom_field") or item.get("seller_sku") or "unknown"
        routes.append({
            "supplier": "mock_supplier",
            "sku": sku,
            "quantity": item.get("quantity", 1),
            "action": "send_to_supplier"
        })

    return {
        "order_id": order.get("external_order_id"),
        "ready": len(routes) > 0,
        "routes": routes
    }


def workflow():
    return [
        "Webhook recebido do Mercado Livre",
        "Evento salvo em events",
        "Pedido consultado/normalizado",
        "SKU mapeado no catálogo",
        "Fornecedor identificado",
        "Pedido enviado ao fornecedor",
        "Rastreio retornado",
        "Marketplace atualizado"
    ]