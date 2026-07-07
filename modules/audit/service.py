from datetime import datetime
import uuid

def build_event(event_type: str, message: str, payload: dict | None = None):
    return {
        "id": str(uuid.uuid4()),
        "event_type": event_type,
        "message": message,
        "payload": payload or {},
        "created_at": datetime.utcnow().isoformat()
    }

def audit_status():
    return {
        "success": True,
        "module": "Audit / Logs",
        "events_supported": [
            "product_created",
            "supplier_created",
            "inventory_sync",
            "pricing_update",
            "marketplace_publish",
            "order_received",
            "ai_optimization",
            "full_sync"
        ]
    }