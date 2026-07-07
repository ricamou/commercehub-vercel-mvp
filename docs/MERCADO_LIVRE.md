# Mercado Livre — Milestone 1

## URLs

Redirect URI:

```text
https://commercehub-vercel-mvp.vercel.app/mercadolivre/callback
```

Webhook:

```text
https://commercehub-vercel-mvp.vercel.app/api/webhooks/mercadolivre
```

## Fluxo

1. Usuário clica em conectar.
2. Mercado Livre autentica.
3. Mercado Livre retorna para callback.
4. CommerceHub troca `code` por token.
5. Usuário copia tokens para Vercel.

## Próxima etapa

Adicionar banco externo para salvar tokens automaticamente.
