# CommerceHub Enterprise — Supabase Stable Fix

Correção definitiva para o erro 500 causado por falha de conexão Supabase/httpx.

## Erro corrigido

`httpx.ConnectError: [Errno 16] Device or resource busy`

Antes, quando o Supabase falhava temporariamente, a aplicação caía com Internal Server Error.

Agora:
- db_select não derruba o sistema
- db_insert não derruba o sistema
- db_upsert não derruba o sistema
- a aplicação mostra erro controlado
- endpoints continuam abrindo

## Testes depois do deploy

- `/api/health`
- `/`
- `/supabase`
- `/api/supabase/ready`
- `/api/foundation/status`
- `/products`
- `/suppliers`

Se aparecer `supabase_error`, o problema é conexão/variável/tabela, mas o site não deve mais cair com 500.
