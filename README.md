# CommerceHub Enterprise V5 - Sprint 19 Listing Engine Mercado Livre

## Entregue
- Listing Engine em `/listing-engine`
- Criação de rascunho a partir do Product Master
- Predição de categoria do Mercado Livre
- Consulta dos atributos da categoria
- Tipos de anúncio disponíveis
- Validação local antes da publicação
- Publicação real via `POST /items`
- Descrição via recurso do item
- Sincronização de preço e estoque
- Histórico de publicação e erros
- Confirmação explícita `PUBLICAR`
- Nenhuma publicação automática

## Instalação
1. Envie todos os arquivos ao GitHub Web.
2. Aguarde o deploy da Vercel.
3. Confirme `/api/health`.
4. Faça login.
5. Abra `/listing-engine/sql`.
6. Copie todo o SQL.
7. Supabase > SQL Editor > New query > cole > Run.
8. Abra `/api/listing-engine/status`.
9. Abra `/product-master`.
10. Abra um produto e clique em `Criar anúncio ML`.
11. Salve o rascunho e corrija os avisos.
12. A publicação real exige digitar `PUBLICAR`.

## Versão esperada
`enterprise-v5-sprint19-listing-engine-mercado-livre`

## Rotas principais
- `/listing-engine`
- `/listing-engine/sql`
- `/product-master/{id}/listing`
- `/listing-engine/{id}`
- `/api/ml/category-predict?q=produto`
- `/api/ml/categories/{category_id}/attributes`
- `/api/ml/listing-types`
- `/api/listing-engine/status`

## Segurança operacional
O sistema nunca publica ao abrir uma página ou executar um teste.
A publicação real exige:
- anúncio sem erros locais;
- conta Mercado Livre conectada;
- confirmação manual digitando `PUBLICAR`.

## Limite GitHub Web
Pacote mantido abaixo de 100 arquivos.
