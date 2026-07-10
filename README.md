# CommerceHub Enterprise V5 - Sprint 18 Product Master

## Entregue
- Catálogo Mestre em `/product-master`
- Busca por SKU, EAN, nome e marca
- Filtro de status e paginação
- Criação e edição de produto mestre
- SKU interno, EAN/GTIN, SEO, descrições, NCM e garantia
- Peso e dimensões
- Imagem principal e galeria
- Atributos do produto
- Múltiplos fornecedores por produto
- Histórico de alterações
- Status de sincronização para marketplaces
- Vinculação automática com ofertas da Sprint 17
- API de busca e status técnico

## Instalação
1. Envie todos os arquivos ao GitHub Web.
2. Aguarde o deploy da Vercel.
3. Confirme `/api/health`.
4. Faça login.
5. Abra `/product-master/sql`.
6. Copie todo o SQL.
7. Supabase > SQL Editor > New query > cole > Run.
8. Abra `/api/product-master/status`.
9. Abra `/product-master`.
10. Abra um produto e teste edição, imagens e atributos.

## Versão esperada
`enterprise-v5-sprint18-product-master`

## Rotas principais
- `/product-master`
- `/product-master/new`
- `/product-master/sql`
- `/product-master/{id}`
- `/product-master/{id}/edit`
- `/product-master/{id}/images`
- `/product-master/{id}/attributes`
- `/api/product-master/status`
- `/api/product-master/search?q=mouse`

## Limite GitHub Web
Pacote mantido abaixo de 100 arquivos.
