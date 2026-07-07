# CommerceHub SIMPLE WORKING v1

Versão reduzida e funcional do CommerceHub, com menos de 30 arquivos para upload no GitHub Web.

## Funcionalidades mantidas

- Dashboard
- Mercado Livre OAuth/API
- Consulta `/users/me`
- Busca de categorias do Mercado Livre
- Webhook Mercado Livre
- Fornecedor simulado
- Importação de produtos
- Catálogo
- Preview de anúncio
- Publicação teste
- Pedidos simulados
- Relatórios financeiros
- Pricing, Inventory e AI simples

## Rotas web

- `/dashboard`
- `/mercado-livre`
- `/fornecedores`
- `/produtos`
- `/anuncios`
- `/pedidos`
- `/relatorios`
- `/arquitetura`

## Rotas API principais

- `/api/health`
- `/api/mercadolivre/me`
- `/api/mercadolivre/categories/search?q=suporte celular`
- `POST /api/fornecedores/mock/import`
- `/api/anuncios/preview/SUP-001?category_id=MLBXXXX`
- `POST /api/pedidos/simulate`
- `/api/relatorios/finance`
