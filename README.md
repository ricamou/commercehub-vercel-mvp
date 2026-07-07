# CommerceHub v2 Inventory Sync v1

Versão com Inventory Sync: estoque, preview de fornecedor e payload para Mercado Livre.

## Adicionado

- Página `/inventory-sync`
- Relatório de estoque
- Preview de estoque do fornecedor
- Plano de sincronização
- Payload para atualização de estoque no Mercado Livre
- Registro de evento de sincronização no Supabase quando configurado

## Endpoints

- GET `/api/inventory/report`
- GET `/api/inventory/supplier-preview`
- GET `/api/inventory/sync-plan`
- GET `/api/inventory/ml-payload/SUP-001?stock=10`
- POST `/api/inventory/sync-event`

## Próximo passo

Pricing Automation v1:
- recalcular preço com margem
- gerar payload de preço para Mercado Livre
- registrar evento de alteração de preço
