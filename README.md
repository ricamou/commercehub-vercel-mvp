# CommerceHub Enterprise — Dashboard Safe Fix

Correção da página inicial `/`.

## Corrigido

- `/` não consulta mais Supabase diretamente.
- `/` não cai mais com Internal Server Error.
- `/dashboard` aponta para o mesmo painel seguro.
- Adicionado `/api/root-test`.
- Adicionados `/favicon.ico` e `/favicon.png` para reduzir logs 404.

## Testes

- `/api/health`
- `/`
- `/dashboard`
- `/api/root-test`
- `/supabase`
- `/api/backend/health`
- `/products`
- `/suppliers`
