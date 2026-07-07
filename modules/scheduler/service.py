DEFAULT_JOBS = [
    {"id": "sync_inventory", "name": "Sincronizar estoque", "frequency": "manual/cron-ready", "status": "ready"},
    {"id": "sync_prices", "name": "Sincronizar preços", "frequency": "manual/cron-ready", "status": "ready"},
    {"id": "import_suppliers", "name": "Importar fornecedores", "frequency": "manual/cron-ready", "status": "ready"},
    {"id": "check_orders", "name": "Verificar pedidos", "frequency": "manual/cron-ready", "status": "ready"},
]

def scheduler_status():
    return {
        "success": True,
        "module": "Scheduler",
        "jobs": DEFAULT_JOBS,
        "note": "Na Vercel, execução automática deve usar Vercel Cron Jobs ou serviço externo."
    }

def job_plan(job_id: str):
    job = next((j for j in DEFAULT_JOBS if j["id"] == job_id), None)
    if not job:
        return {"success": False, "message": "Job não encontrado."}
    return {"success": True, "job": job, "execution_mode": "manual_ready"}