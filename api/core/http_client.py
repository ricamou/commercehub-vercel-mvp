import json
import urllib.request
import urllib.error

def parse_json(raw, default):
    try:
        if not raw:
            return default
        return json.loads(raw)
    except Exception:
        return default

def request_json(method, url, headers=None, payload=None, timeout=12):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method.upper(), headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            return {"success": 200 <= resp.status < 400, "status_code": resp.status, "data": parse_json(raw, {}), "raw": raw, "error": ""}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        return {"success": False, "status_code": exc.code, "data": parse_json(raw, {}), "raw": raw, "error": raw or str(exc)}
    except Exception as exc:
        return {"success": False, "status_code": 0, "data": {}, "raw": "", "error": str(exc)}
