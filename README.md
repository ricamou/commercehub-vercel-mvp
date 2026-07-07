# CommerceHub Final Production Ready

Versão final consolidada para GitHub Web e Vercel.

## Arquivos
Total: 6 arquivos.

- api/index.py
- requirements.txt
- vercel.json
- .env.example
- supabase_schema.sql
- README.md

## Testes principais

- /api/health
- /dashboard
- /enterprise-final
- /sprint1
- /sprint2
- /sprint3
- /mercado-livre
- /produtos
- /anuncios
- /relatorios
- /ai
- /database

## APIs principais

- GET /api/connectors/status
- POST /api/connectors/parse/json
- POST /api/connectors/parse/csv
- POST /api/connectors/parse/xml
- POST /api/import/from-payload/json
- GET /api/sync/compare
- GET /api/sync/marketplace-payload
- POST /api/sync/run-demo
- GET /api/anuncios/preview/SUP-001?category_id=MLBXXXX
- GET /api/mercadolivre/status
- GET /api/database/status

## Observação

Esta versão foi consolidada em um único backend para evitar problemas de importação na Vercel e manter o projeto abaixo do limite do GitHub Web.
