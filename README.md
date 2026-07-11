# CommerceHub Enterprise V5 — Sprint 25.1 Auto Learning Preflight

Esta versão aprende regras também a partir do Metadata Preflight e dos
atributos condicionais retornados pelo Mercado Livre, sem exigir uma nova
falha no POST /items.

## Resultado esperado no produto atual

- Regras aprendidas: pelo menos 1
- Status: BLOQUEADO
- Regra: GTIN_REQUIRED
- Fonte: mercado_livre_conditional_metadata ou legacy_marketplace_feedback

## Instalação

1. Envie os arquivos pelo GitHub Web.
2. Aguarde o deploy.
3. Confirme `/api/health`.
4. Não execute novo SQL.
5. Abra Marketplace Intelligence.
6. Clique em `Atualizar inteligência`.
