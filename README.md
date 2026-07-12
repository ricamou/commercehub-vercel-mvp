# CommerceHub Enterprise V5 — Sprint 27

Continuação direta da Sprint 26 Publishing Lab.

## Novo módulo

**Auto Correction Engine**: lê os bloqueios do fluxo de publicação, corrige automaticamente os itens determinísticos e executa novamente o Publishing Lab.

Acesse um anúncio pelo Listing Engine e abra o Publishing Lab para usar **Corrigir automaticamente**.

Consulte `PASSO_A_PASSO_SPRINT27.txt`.

## Sprint 30.2 — Correção do pipeline de imagens

A imagem importada agora é promovida de `raw_data.image_url` para
`products.primary_image_url` e `product_images`. O Workflow também tenta espelhar
a imagem no Supabase Storage antes do Publishing Lab. Consulte
`AUDITORIA_E_CORRECAO_IMAGENS_SPRINT30_2.txt`.
