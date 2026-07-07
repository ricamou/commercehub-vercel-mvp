from core import config

def status():
    return {
        "supabase_configured": bool(getattr(config, "SUPABASE_URL", "") and getattr(config, "SUPABASE_SERVICE_ROLE_KEY", "")),
        "mode": "supabase_ready" if getattr(config, "SUPABASE_URL", "") and getattr(config, "SUPABASE_SERVICE_ROLE_KEY", "") else "memory_demo",
        "message": "Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY na Vercel para banco persistente."
    }
