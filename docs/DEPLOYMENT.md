# Deploy CommerceHub

## Plataforma

Vercel.

## Variáveis necessárias

```text
APP_NAME=CommerceHub
APP_ENV=production
DEFAULT_MARGIN_PERCENT=35
ML_COMMISSION_PERCENT=16
FIXED_OPERATIONAL_COST=6.00
ML_CLIENT_ID=
ML_CLIENT_SECRET=
ML_REDIRECT_URI=https://commercehub-vercel-mvp.vercel.app/mercadolivre/callback
ML_ACCESS_TOKEN=
ML_REFRESH_TOKEN=
ML_TOKEN_EXPIRES_IN=
ML_USER_ID=
```

## Fluxo de deploy

```bash
git add .
git commit -m "Release v0.5"
git push
```

A Vercel fará o deploy automaticamente.
