# CommerceHub FINAL OAuth Refresh Fix

Correção aplicada:

- `/api/mercadolivre/me` agora tenta renovar o token automaticamente se receber 401.
- Novo endpoint: `/api/mercadolivre/refresh-token`.
- Quando o token for renovado, o sistema retorna os novos valores para copiar na Vercel.

## Testes

1. `/api/health`
2. `/api/mercadolivre/status`
3. `/api/mercadolivre/refresh-token`
4. `/api/mercadolivre/me`

## Se `/api/mercadolivre/refresh-token` retornar sucesso

Copie os novos valores para a Vercel:

- ML_ACCESS_TOKEN
- ML_REFRESH_TOKEN
- ML_USER_ID
- ML_TOKEN_EXPIRES_IN

Depois faça Redeploy.
