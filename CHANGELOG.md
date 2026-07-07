# Changelog

## Milestone 1

### Added
- OAuth Mercado Livre completo.
- Webhook Mercado Livre.
- Endpoint `/api/webhooks/mercadolivre`.
- Endpoint `/api/mercadolivre/auth-url`.
- Endpoint `/api/mercadolivre/me`.
- Endpoint `/api/mercadolivre/token-status`.
- Endpoint `/api/mercadolivre/refresh-token`.
- Tela de callback com instruções para copiar tokens.
- Tela Mercado Livre com status de credenciais e tokens.

### Notes
- Tokens ainda são configurados manualmente na Vercel após o primeiro callback.
- Banco de dados externo será adicionado em etapa futura.
