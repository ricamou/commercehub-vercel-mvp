
# Sprint 11 - Enterprise Debug Mode

Adicione um handler global de exceções ao FastAPI:

```python
from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    tb = traceback.format_exc()
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error_type": type(exc).__name__,
            "message": str(exc),
            "path": str(request.url.path),
            "traceback": tb,
        },
    )
```

Envolva também rotas críticas:

```python
@app.get("/api/core/status")
async def core_status():
    try:
        # código existente
        ...
    except Exception as exc:
        import traceback
        return {
            "success": False,
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
```

Repita o padrão para:
- /api/test/supabase
- /api/test/supabase-insert
- /api/test/supabase-crud
- /api/database/schema-check
- /api/core/create-test-product

Objetivo:
Toda exceção deve retornar JSON detalhado em vez de "Internal Server Error".
