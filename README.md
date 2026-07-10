# CommerceHub Enterprise V5 — Sprint 22 Intelligent GTIN Resolver

## Entregue

- Consulta automática das opções de `EMPTY_GTIN_REASON`
- Dropdown com os valores permitidos pelo Mercado Livre
- Gravação de `value_id` e `value_name`
- Modo “produto possui GTIN”
- Modo “produto não possui GTIN”
- Exclusão automática do atributo conflitante
- Ao escolher GTIN:
  - salva GTIN válido
  - remove `EMPTY_GTIN_REASON`
- Ao escolher produto sem GTIN:
  - salva `EMPTY_GTIN_REASON`
  - remove GTIN
  - limpa o EAN inválido do Product Master
- O Smart Category não volta a sugerir o GTIN inválido
- Endpoint de diagnóstico do resolvedor

## Instalação

1. Envie todos os arquivos pelo GitHub Web.
2. Aguarde o deploy.
3. Abra `/api/health`.
4. Confirme a versão:
   `enterprise-v5-sprint22-intelligent-gtin-resolver`
5. Não é necessário executar novo SQL.
6. Abra o produto → anúncio → Atributos inteligentes.
7. Use o painel “Resolvedor inteligente de GTIN”.
8. Escolha:
   - GTIN real; ou
   - produto sem GTIN + motivo permitido.
9. Valide os requisitos.
10. Publique.

## Endpoints

- `/api/gtin-resolver/category/{category_id}/options`
- `/api/gtin-resolver/product/{product_id}/category/{category_id}/status`
