# CommerceHub v2 STABLE

Versão estável e consolidada para Vercel/GitHub Web.

## Importante

Esta versão foi refeita para evitar erro de imports entre módulos.
Todo o núcleo está concentrado em `api/index.py`, mantendo o projeto pequeno e estável.

## Arquivos

- api/index.py
- requirements.txt
- vercel.json
- .env.example
- README.md

Total: 5 arquivos.

## Testes

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

## APIs principais

- GET /api/connectors/status
- POST /api/connectors/parse/json
- POST /api/import/from-payload/json
- GET /api/sync/compare
- GET /api/sync/marketplace-payload
- POST /api/sync/run-demo
- GET /api/anuncios/preview/SUP-001?category_id=MLBXXXX
