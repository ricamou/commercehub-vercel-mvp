# CommerceHub Enterprise V3 Core

Fundação definitiva do CommerceHub.

## Banco definitivo

- companies
- users
- suppliers
- products
- inventory
- orders
- listings
- oauth_tokens
- logs
- ai_history
- queue
- webhooks
- sync_jobs

## Fluxo

Supabase → Cadastro único → Tela → Mercado Livre / Shopee / Amazon

## Testes

- /api/health
- /api/foundation/status
- /foundation
- /api/foundation/seed
- /companies
- /users
- /suppliers
- /products
- /inventory
- /orders
- /listings
- /logs
- /queue
- /sync
- /mercado-livre
- /api/mercadolivre/me
- /api/ml/items
- /api/ml/orders

## Passo obrigatório

Rode `supabase_schema.sql` no Supabase e configure na Vercel:

- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
