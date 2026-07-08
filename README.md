# CommerceHub Enterprise — Backend Reviewed Stable

Backend refeito de forma estável para Vercel.

## Correções

- Rotas principais sem Internal Server Error.
- Cliente Supabase defensivo usando urllib.
- Timeout e retry controlado.
- Health checks seguros.
- Mercado Livre com chamadas controladas.
- Telas principais independentes de crash do banco.

## Testes

- /api/health
- /
- /dashboard
- /supabase
- /api/supabase/ready
- /api/backend/health
- /api/backend/stress-light
- /api/foundation/status
- /products
- /suppliers
- /inventory
- /mercado-livre
