# CommerceHub Enterprise V5 — Sprint 40 Order Center

## Recursos

- painel central de pedidos;
- sincronização manual dos pedidos mais recentes;
- consulta do pedido completo;
- identificação de fornecedor;
- status do pagamento;
- etapa operacional;
- itens e quantidades;
- jobs do fornecedor;
- nota fiscal e rastreamento;
- linha do tempo de eventos.

## Rotas

- `/order-center`
- `/order-center/{ORDER_ID}`
- `POST /api/order-center/sync`
- `GET /api/order-center/orders`
- `GET /api/order-center/orders/{ORDER_ID}`

## Versão

`enterprise-v5-sprint40-order-center`

## Supabase

Não é necessária nova query. A Sprint 40 reutiliza as tabelas da Sprint 39.
