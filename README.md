# CommerceHub FINAL Supabase OAuth

Agora os tokens do Mercado Livre são salvos no Supabase e renovados automaticamente.

## O que mudou

- Nova tabela: `oauth_tokens`
- Callback salva o token no Supabase
- `/api/mercadolivre/me` busca token no Supabase
- Se o token expirar, o sistema usa o refresh token e salva o novo token
- Novo endpoint: `/api/mercadolivre/token-store`
- Novo endpoint: `/api/mercadolivre/refresh-token`

## Passo obrigatório

No Supabase SQL Editor, rode o conteúdo do arquivo:

`supabase_schema.sql`

Depois confirme que a Vercel tem:

- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
- ML_CLIENT_ID
- ML_CLIENT_SECRET
- ML_REDIRECT_URI=https://commercehub-vercel-mvp.vercel.app/mercadolivre/callback

## Testes

- /api/health
- /api/database/status
- /api/mercadolivre/oauth-config
- /mercado-livre
- /api/mercadolivre/token-store
- /api/mercadolivre/refresh-token
- /api/mercadolivre/me
