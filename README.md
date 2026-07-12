# CommerceHub Enterprise V5 — Sprint 28

Continuação direta da Sprint 26 Publishing Lab.

## Novo módulo

**Auto Correction Engine**: lê os bloqueios do fluxo de publicação, corrige automaticamente os itens determinísticos e executa novamente o Publishing Lab.

Acesse um anúncio pelo Listing Engine e abra o Publishing Lab para usar **Corrigir automaticamente**.

Consulte `PASSO_A_PASSO_SPRINT28.txt`.

## Sprint 28 — Enrichment Resolver

O fluxo de publicação agora tenta enriquecer o produto pelo catálogo oficial do Mercado Livre antes da correção e auditoria. A correspondência precisa atingir confiança mínima; GTIN só é aplicado quando válido e com confiança elevada. Dados ambíguos permanecem bloqueados para revisão.

Fluxo: Product Master → Enrichment Resolver → Auto Correction Engine → Publishing Lab → Publicação.
