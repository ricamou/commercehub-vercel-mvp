import csv, io, json, xml.etree.ElementTree as ET

try:
    import httpx
except Exception:
    httpx = None

SUPPORTED_CONNECTORS = [
    {"type": "api_rest", "name": "API REST", "status": "ready"},
    {"type": "json", "name": "JSON Payload", "status": "ready"},
    {"type": "xml", "name": "XML Feed", "status": "ready"},
    {"type": "csv", "name": "CSV / Planilha", "status": "ready"},
    {"type": "ftp", "name": "FTP / SFTP", "status": "prepared"},
]

FIELD_MAP = {
    "sku": ["sku", "codigo", "id", "code", "reference", "ref"],
    "name": ["name", "nome", "title", "titulo", "produto", "product_name"],
    "brand": ["brand", "marca", "manufacturer"],
    "ean": ["ean", "gtin", "barcode", "codigo_barras"],
    "category": ["category", "categoria", "department", "departamento"],
    "description": ["description", "descricao", "desc", "details"],
    "cost_price": ["cost_price", "custo", "preco_custo", "price_cost", "wholesale_price"],
    "stock": ["stock", "estoque", "quantity", "qty", "available_quantity"],
    "image_url": ["image_url", "imagem", "image", "picture", "photo"],
}

def connector_status():
    return {"success": True, "module": "Universal Supplier Connector", "version": "sprint1", "connectors": SUPPORTED_CONNECTORS}

def find_field(payload, names):
    lower = {str(k).lower(): v for k, v in dict(payload or {}).items()}
    for name in names:
        if name in payload and payload.get(name) not in [None, ""]:
            return payload.get(name)
        if name.lower() in lower and lower.get(name.lower()) not in [None, ""]:
            return lower.get(name.lower())
    return ""

def to_float(value):
    try:
        if isinstance(value, str):
            value = value.replace("R$", "").replace(".", "").replace(",", ".").strip()
        return float(value or 0)
    except Exception:
        return 0.0

def to_int(value):
    try:
        return int(float(str(value or 0).replace(",", ".")))
    except Exception:
        return 0

def normalize_supplier_product(payload, source_type="manual"):
    payload = payload or {}
    return {
        "source_type": source_type,
        "sku": str(find_field(payload, FIELD_MAP["sku"])).strip(),
        "name": str(find_field(payload, FIELD_MAP["name"])).strip(),
        "brand": str(find_field(payload, FIELD_MAP["brand"])).strip(),
        "ean": str(find_field(payload, FIELD_MAP["ean"])).strip(),
        "category": str(find_field(payload, FIELD_MAP["category"])).strip(),
        "description": str(find_field(payload, FIELD_MAP["description"])).strip(),
        "cost_price": to_float(find_field(payload, FIELD_MAP["cost_price"])),
        "stock": to_int(find_field(payload, FIELD_MAP["stock"])),
        "image_url": str(find_field(payload, FIELD_MAP["image_url"])).strip(),
        "raw_data": payload,
    }

def validate_product(product):
    missing = [f for f in ["sku", "name"] if not product.get(f)]
    warnings = []
    if not product.get("ean"): warnings.append("EAN/GTIN ausente.")
    if product.get("cost_price", 0) <= 0: warnings.append("Custo ausente ou zerado.")
    if product.get("stock", 0) <= 0: warnings.append("Estoque ausente ou zerado.")
    return {"valid": len(missing) == 0, "missing": missing, "warnings": warnings}

def preview_connector_payload(payload, source_type="manual"):
    normalized = normalize_supplier_product(payload, source_type)
    return {"success": True, "source_type": source_type, "normalized": normalized, "validation": validate_product(normalized)}

def parse_json_payload(payload):
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("products") or payload.get("items") or payload.get("data") or [payload]
    else:
        items = []
    return [normalize_supplier_product(item, "json") for item in items]

def parse_csv_payload(text):
    return [normalize_supplier_product(row, "csv") for row in csv.DictReader(io.StringIO(str(text)))]

def parse_xml_payload(text):
    root = ET.fromstring(str(text))
    candidates = root.findall(".//product") or root.findall(".//produto") or root.findall(".//item") or list(root)
    products = []
    for node in candidates:
        data = {child.tag: child.text for child in list(node)}
        if data:
            products.append(normalize_supplier_product(data, "xml"))
    return products

def parse_payload_by_type(source_type, payload):
    source_type = (source_type or "json").lower()
    if source_type in ["json", "api_rest", "api"]:
        products = parse_json_payload(payload)
    elif source_type == "csv":
        products = parse_csv_payload(payload if isinstance(payload, str) else payload.get("payload", ""))
    elif source_type == "xml":
        products = parse_xml_payload(payload if isinstance(payload, str) else payload.get("payload", ""))
    else:
        products = [normalize_supplier_product(payload if isinstance(payload, dict) else {}, source_type)]
    return {"success": True, "source_type": source_type, "count": len(products), "products": products, "validation": [validate_product(p) for p in products]}

async def fetch_api_products(url, headers=None):
    if not httpx:
        return {"success": False, "message": "httpx não instalado."}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=headers or {})
        data = response.json()
    products = parse_json_payload(data)
    return {"success": response.status_code < 400, "status_code": response.status_code, "count": len(products), "products": products}