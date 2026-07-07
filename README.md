# CommerceHub Sprint 2 — Supplier Product Import Persistent v1

## Objetivo

Importar produtos reais de fornecedores e persistir no Supabase/PostgreSQL.

## Adicionado

- Persistência de produtos importados
- Separação de produtos válidos e inválidos
- Resumo de importação
- Registro de evento de importação
- Fallback em modo demo quando Supabase não está configurado

## Testes

- /sprint2
- /api/import/summary/mock
- POST /api/import/persist/json
- POST /api/import/persist/csv
- POST /api/import/persist/xml
- POST /api/import/event

## Próxima sprint

Supplier Sync Automation:
- sincronizar estoque/custo
- detectar alterações
- atualizar catálogo
- gerar eventos de sync
