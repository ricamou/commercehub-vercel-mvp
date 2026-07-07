# CommerceHub v2 Marketplace Operations v1

Versão com camada operacional de marketplace.

## Adicionado

- Página `/marketplace-ops`
- Status operacional de marketplaces
- Plano de operação
- Preview operacional por SKU
- Integração com Listing, Pricing e Inventory
- Registro de evento operacional no Supabase quando configurado

## Endpoints

- GET `/api/marketplace-ops/status`
- GET `/api/marketplace-ops/plan`
- GET `/api/marketplace-ops/preview/SUP-001?category_id=MLBXXXX`
- POST `/api/marketplace-ops/event`

## Próximo passo

Universal Supplier Connector v1:
- preparar conectores API/XML/CSV/FTP
- importar produtos de fornecedores reais
- mapear produtos para o catálogo mestre
