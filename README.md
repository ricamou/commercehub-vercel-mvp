# CommerceHub — Milestone 1

Sistema para integração:

**Fornecedor Simulado → CommerceHub → Mercado Livre**

## Entrega

Esta versão adiciona a primeira integração real com Mercado Livre:

- OAuth completo
- Botão de conexão
- Callback de autenticação
- Troca de code por token
- Consulta `/users/me`
- Endpoint de webhook obrigatório do Mercado Livre
- Tela Mercado Livre melhorada
- Preparação para publicação teste controlada

## Variáveis na Vercel

Configure em **Settings → Environment Variables**:

```text
APP_NAME=CommerceHub
APP_ENV=production
DEFAULT_MARGIN_PERCENT=35
ML_COMMISSION_PERCENT=16
FIXED_OPERATIONAL_COST=6.00

ML_CLIENT_ID=6835052957272496
ML_CLIENT_SECRET=SUA_CHAVE_SECRETA
ML_REDIRECT_URI=https://commercehub-vercel-mvp.vercel.app/mercadolivre/callback

ML_ACCESS_TOKEN=
ML_REFRESH_TOKEN=
ML_TOKEN_EXPIRES_IN=
ML_USER_ID=
```

## Rotas importantes

```text
/
```

```text
/mercado-livre
```

```text
/mercadolivre/connect
```

```text
/mercadolivre/callback
```

```text
/api/health
```

```text
/api/mercadolivre/status
```

```text
/api/mercadolivre/auth-url
```

```text
/api/mercadolivre/me
```

```text
/api/webhooks/mercadolivre
```

## URL de notificações para o Mercado Livre

Use:

```text
https://commercehub-vercel-mvp.vercel.app/api/webhooks/mercadolivre
```


## Hotfix

Correção para evitar Internal Server Error na tela `/mercado-livre` quando o token estiver inválido, incompleto ou quando a API do Mercado Livre retornar erro.
