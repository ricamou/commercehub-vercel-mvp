# CommerceHub Enterprise V5 — Sprint 22.1 GTIN Resolver UI

## Entregue

- Tela dedicada e simplificada para resolver GTIN
- Rádio “Produto possui GTIN”
- Rádio “Produto não possui GTIN”
- Campo GTIN ativado apenas quando necessário
- Select de motivos ativado apenas quando necessário
- Motivos carregados dos metadados do Mercado Livre
- Salvamento no resolvedor já existente da Sprint 22
- Remoção automática do atributo conflitante
- Link `Resolver GTIN` na tela de atributos inteligentes
- Nenhum novo SQL necessário

## Instalação

1. Envie todos os arquivos pelo GitHub Web.
2. Aguarde o deploy.
3. Abra `/api/health`.
4. Confirme:
   `enterprise-v5-sprint22-1-gtin-resolver-ui`
5. Não execute SQL.
6. Abra o produto → anúncio → Atributos inteligentes.
7. Clique em `Resolver GTIN`.
8. Escolha uma das opções e salve.
9. Volte aos atributos, valide e publique.

## Rota nova

`/gtin-resolver/product/{product_id}/category/{category_id}`
