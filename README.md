# CommerceHub Enterprise V5 - Sprint 19 Order Manager

## Entregue
- Gestão de pedidos em `/orders`
- Tela detalhada por pedido
- Importação demonstrativa
- Sincronização real com `/orders/search` do Mercado Livre
- Normalização de comprador, pagamento, envio e itens
- Vinculação de itens por SKU ao catálogo mestre
- Reserva automática de estoque
- Histórico de status
- Logs de sincronização
- Status técnico do módulo
- Proteção pela autenticação Enterprise

## Instalação
1. Suba os arquivos no GitHub Web.
2. Aguarde o deploy Vercel.
3. Confirme `/api/health`.
4. Faça login.
5. Abra `/orders/sql`.
6. Copie o SQL e execute em uma nova query no Supabase.
7. Abra `/api/orders/status`.
8. Abra `/api/orders/demo-import`.
9. Confira `/orders`, `/inventory` e `/logs`.
10. Com o Mercado Livre conectado, use `/api/orders/sync-mercadolivre`.

## Versão esperada
`enterprise-v5-sprint19-order-manager`

## Observação
A sincronização real usa o vendedor autenticado e consulta os pedidos do Mercado Livre.
A importação demonstrativa permite validar todo o módulo antes de existir uma venda real.

## Limite GitHub Web
Pacote mantido abaixo de 100 arquivos.
