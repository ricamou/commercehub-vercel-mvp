# CommerceHub - Configuração correta das variáveis na Vercel

Caminho: Project > Settings > Environment Variables

SUPABASE_URL = Project URL do Supabase. Formato: https://xxxxxxxxxxxxxxxxxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY = service_role secret key. Backend only.
SUPABASE_ANON_KEY = anon public key.
ML_CLIENT_ID = Client ID do app Mercado Livre.
ML_CLIENT_SECRET = Client Secret do app Mercado Livre.
ML_REDIRECT_URI = https://commercehub-vercel-mvp.vercel.app/mercadolivre/callback

Depois de alterar: faça Redeploy obrigatório.

Testes:
/api/health
/environment
/api/environment/full
/api/raw/full
/api/test/supabase
/api/test/supabase-insert
