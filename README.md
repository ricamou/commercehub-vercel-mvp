# CommerceHub Enterprise — Home Final Fix

Correção definitiva da rota `/`.

## O que foi feito

- Removidas rotas antigas de `/` e `/dashboard`.
- Criada uma home ultra segura que não consulta Supabase.
- Criada `/dashboard` com o mesmo HTML seguro.
- Criado `/api/root-test`.
- Criados `/favicon.ico` e `/favicon.png`.

## Testes

- `/api/health`
- `/`
- `/dashboard`
- `/api/root-test`
- `/supabase`
- `/api/backend/health`
- `/products`
- `/suppliers`
