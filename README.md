# CommerceHub Enterprise V5 — Sprint 24 Marketplace Metadata Preflight

## Pesquisa aplicada

A implementação foi orientada por documentação oficial do Mercado Livre:

- validações por atributos da categoria;
- `conditional_required`;
- User Products com `family_name`;
- validação e uso de identificadores GTIN.

Também foi considerada a recomendação da GS1 de validar se o GTIN está realmente vinculado ao produto, e não apenas se possui dígito verificador válido.

## O que foi corrigido

- `CATEGORY_RULE_GTIN_REQUIRED` e qualquer outro atributo interno nunca mais serão enviados ao Mercado Livre;
- somente IDs existentes nos metadados oficiais da categoria entram no payload;
- a regra aprendida de GTIN agora é consultada corretamente por produto e categoria;
- o sistema tenta consultar a validação condicional antes do `POST /items`;
- o anúncio é bloqueado localmente quando uma regra oficial ou aprendida não é atendida;
- nova tela `Metadata Preflight`;
- novo JSON técnico de diagnóstico.

## Instalação

1. Envie todos os arquivos pelo GitHub Web.
2. Aguarde o deploy.
3. Abra `/api/health`.
4. Confirme:
   `enterprise-v5-sprint24-marketplace-metadata-preflight`
5. Não execute novo SQL.
6. Abra o anúncio.
7. Clique em `Metadata Preflight`.
8. Corrija os bloqueios apresentados.
9. Só então publique.

## Rotas novas

- `/metadata-preflight/listing/{listing_id}`
- `/api/metadata-preflight/listing/{listing_id}`
