# CommerceHub Enterprise — Root Fix

Correção da rota principal `/`.

## Corrigido

- `/` volta a abrir o Dashboard.
- `/dashboard` também abre o Dashboard.
- Novo endpoint `/api/routes` para listar rotas publicadas.
- Mantém Backend Hardened para Supabase.

## Testes

- `/api/health`
- `/`
- `/dashboard`
- `/api/routes`
- `/supabase`
- `/api/backend/health`
- `/products`
- `/suppliers`
