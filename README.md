# CommerceHub Enterprise FULL READY

Versão consolidada do sistema comercial.

## Inclui

- Banco definitivo Supabase
- Login de usuários
- Multiempresa
- Fornecedores
- Produtos
- Estoque
- Pedidos
- Anúncios
- OAuth Tokens
- Logs
- AI History
- Filas
- Webhooks
- Sync Jobs
- Mercado Livre funcional
- Shopee preparado
- Amazon SP-API preparado
- Magalu preparado
- IA para título, descrição, SEO e preço
- Dashboard profissional
- Relatórios
- Sincronização em tempo real

## Testes principais

- /api/health
- /api/foundation/status
- /foundation
- /api/foundation/seed
- /
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

## Banco

Rode `supabase_schema.sql` no Supabase.

Depois configure na Vercel:

- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
