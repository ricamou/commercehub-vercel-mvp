# CommerceHub Enterprise Real v1

Versão com Mercado Livre real nas telas principais.

## O que mudou

- Nova tela `/real`
- Produtos lendo anúncios reais do Mercado Livre
- Anúncios lendo anúncios reais do Mercado Livre
- Pedidos lendo pedidos reais do Mercado Livre
- Dashboard real via `/api/ml/dashboard`
- Endpoints reais:
  - `/api/ml/items`
  - `/api/ml/items/{item_id}`
  - `/api/ml/items/{item_id}/description`
  - `/api/ml/orders`
  - `PUT /api/ml/items/{item_id}/price-stock`
  - `PUT /api/ml/items/{item_id}/pause`

## Testes finais

- `/api/health`
- `/api/final-check`
- `/real`
- `/api/ml/dashboard`
- `/api/ml/items`
- `/api/ml/orders`
- `/produtos`
- `/anuncios`
- `/pedidos`

## Observação

Se sua conta ainda não tiver anúncios ou pedidos, as telas aparecerão vazias, mas a conexão estará funcionando.
