# CommerceHub FINAL ENGINEER FIX

Correção final preparada como engenheiro do projeto.

## O que foi arrumado

- Mantém o projeto pequeno para GitHub Web.
- Adiciona `/setup` com o SQL visível dentro do próprio sistema.
- Adiciona `/api/setup/sql`.
- Corrige callback Mercado Livre em `/mercadolivre/callback`.
- Adiciona store de tokens via Supabase.
- Mantém fallback por Environment Variables.
- Adiciona `/api/mercadolivre/token-store`.
- Adiciona `/api/mercadolivre/refresh-token`.
- `/api/mercadolivre/me` tenta renovar token automaticamente se receber 401.

## Depois de subir

Teste:

- /api/health
- /setup
- /api/setup/sql
- /api/database/status
- /api/mercadolivre/oauth-config
- /api/mercadolivre/token-store
- /api/mercadolivre/refresh-token
- /api/mercadolivre/me

## Supabase

O arquivo `supabase_schema.sql` está incluído.
Ele cria a tabela `oauth_tokens`, necessária para salvar tokens automaticamente.
