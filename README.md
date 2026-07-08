# CommerceHub Enterprise — Supabase Final Fix

Correção final para diagnóstico e conexão Supabase.

## O que foi ajustado

- Aceita `SUPABASE_URL` e também `NEXT_PUBLIC_SUPABASE_URL`.
- Aceita `SUPABASE_SERVICE_ROLE_KEY` e também `SUPABASE_KEY` ou `SUPABASE_ANON_KEY`.
- Nova página `/supabase`.
- Novos endpoints:
  - `/api/supabase/diagnostics`
  - `/api/supabase/test`
  - `/api/supabase/ready`
- `/api/foundation/status` agora mostra exatamente o que falta.

## Testes

- `/api/health`
- `/supabase`
- `/api/supabase/diagnostics`
- `/api/supabase/test`
- `/api/supabase/ready`
- `/api/foundation/status`

## Para ficar `mode: supabase`

Na Vercel precisa existir:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Depois faça Redeploy.
