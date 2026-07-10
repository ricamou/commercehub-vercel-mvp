# CommerceHub Enterprise V5 — Sprint 23 Intelligent Category Rules

## O que esta versão faz

- consulta as regras de GTIN da categoria;
- identifica se GTIN é obrigatório;
- identifica se a categoria aceita `EMPTY_GTIN_REASON`;
- bloqueia a publicação antes da API quando a regra não é atendida;
- aprende com erros reais retornados pelo Mercado Livre;
- registra que a categoria exige GTIN quando o ML confirmar isso;
- cria uma tela de diagnóstico por produto e categoria;
- adiciona o botão `Regras da categoria` no anúncio.

## Resultado esperado para o caso atual

Para a categoria `MLB1714`, depois do retorno real do Mercado Livre:

- o CommerceHub registra que GTIN é obrigatório;
- bloqueia novas tentativas usando apenas `EMPTY_GTIN_REASON`;
- mostra a orientação para informar GTIN válido ou trocar a categoria.

## Instalação

1. Envie todos os arquivos pelo GitHub Web.
2. Aguarde o deploy.
3. Abra `/api/health`.
4. Confirme:
   `enterprise-v5-sprint23-intelligent-category-rules`
5. Não execute novo SQL.
6. Abra o anúncio.
7. Clique em `Regras da categoria`.
8. Verifique se o status está liberado ou bloqueado.
9. Corrija GTIN ou categoria conforme a orientação.
10. Publique novamente.

## Rotas novas

- `/api/category-rules/category/{category_id}`
- `/api/category-rules/product/{product_id}/category/{category_id}`
- `/category-rules/product/{product_id}/category/{category_id}`
