# CommerceHub Enterprise V2 — Supabase Persistence

Versão com persistência real preparada para Supabase.

## Agora salva no banco

- Produto salvo no banco
- Fornecedor salvo no banco
- Estoque salvo no banco
- Logs persistidos
- Token Mercado Livre persistido
- Pedido/webhook salvo no banco

## Tabelas

- companies
- users_app
- suppliers
- products
- inventory_movements
- listings
- orders
- events
- oauth_tokens

## Testes

- /api/health
- /api/persistence/status
- /persistence
- POST /api/persistence/seed
- POST /api/persistence/token
- /api/db/products
- /api/db/suppliers
- /api/db/inventory_movements
- /api/db/events
- /api/db/orders
- /api/db/oauth_tokens

## Importante

Para persistência real, configure na Vercel:

- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY

E rode o arquivo `supabase_schema.sql` no SQL Editor do Supabase.
