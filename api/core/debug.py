import time
import uuid
import traceback
import inspect
from fastapi.responses import JSONResponse

def exception_payload(exc, path="", started_at=None, extra=None):
    tb = traceback.format_exc()
    frames = traceback.extract_tb(exc.__traceback__) if getattr(exc, "__traceback__", None) else []
    last = frames[-1] if frames else None
    elapsed_ms = None
    if started_at:
        elapsed_ms = round((time.time() - started_at) * 1000, 2)

    payload = {
        "success": False,
        "error_id": str(uuid.uuid4()),
        "error_type": type(exc).__name__,
        "message": str(exc),
        "path": path,
        "file": last.filename if last else "",
        "line": last.lineno if last else None,
        "function": last.name if last else "",
        "elapsed_ms": elapsed_ms,
        "traceback": tb[-8000:],
    }
    if extra:
        payload["extra"] = extra
    return payload

async def safe_route(fn, path="", extra=None):
    started_at = time.time()
    try:
        result = fn()
        if inspect.isawaitable(result):
            result = await result
        return result
    except Exception as exc:
        return exception_payload(exc, path=path, started_at=started_at, extra=extra)

def json_error_response(request, exc):
    payload = exception_payload(exc, path=str(request.url.path))
    return JSONResponse(status_code=500, content=payload)
