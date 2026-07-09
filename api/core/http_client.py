import json
import httpx

def parse_json(raw, default):
    try:
        if not raw:
            return default
        return json.loads(raw)
    except Exception:
        return default

async def async_request_json(method, url, headers=None, payload=None, timeout=15):
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.request(method.upper(), url, headers=headers or {}, json=payload)
            raw = response.text
            return {
                "success": 200 <= response.status_code < 400,
                "status_code": response.status_code,
                "data": parse_json(raw, {}),
                "raw": raw,
                "error": "" if 200 <= response.status_code < 400 else raw,
                "transport": "httpx-async"
            }
    except Exception as exc:
        return {
            "success": False,
            "status_code": 0,
            "data": {},
            "raw": "",
            "error": str(exc),
            "transport": "httpx-async"
        }

def request_json(method, url, headers=None, payload=None, timeout=15):
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.request(method.upper(), url, headers=headers or {}, json=payload)
            raw = response.text
            return {
                "success": 200 <= response.status_code < 400,
                "status_code": response.status_code,
                "data": parse_json(raw, {}),
                "raw": raw,
                "error": "" if 200 <= response.status_code < 400 else raw,
                "transport": "httpx-sync"
            }
    except Exception as exc:
        return {
            "success": False,
            "status_code": 0,
            "data": {},
            "raw": "",
            "error": str(exc),
            "transport": "httpx-sync"
        }
