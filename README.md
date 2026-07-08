# CommerceHub FINAL OAuth Corrigido

Correção aplicada:

- Adicionada rota `GET /mercadolivre/callback`
- Mantida rota `GET /api/mercadolivre/callback`
- Página visual para copiar tokens do Mercado Livre
- Redirect URI padrão corrigido para `/mercadolivre/callback`
- Endpoint de diagnóstico `/api/mercadolivre/oauth-config`

## Testes depois de subir

- /api/health
- /mercado-livre
- /api/mercadolivre/oauth-config

## Redirect URI Mercado Livre

No Mercado Livre Developers, configure exatamente:

https://commercehub-vercel-mvp.vercel.app/mercadolivre/callback

Depois de conectar, copie para a Vercel:

- ML_ACCESS_TOKEN
- ML_REFRESH_TOKEN
- ML_USER_ID
- ML_TOKEN_EXPIRES_IN

Depois faça Redeploy e teste:

- /api/mercadolivre/status
- /api/mercadolivre/me
