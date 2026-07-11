# CommerceHub Enterprise V5 — Sprint 33.1 GTIN Routing Hotfix

## Correções

- sem variações: `GTIN` em `item.attributes`;
- com variações: `GTIN` em `variations[].attributes`;
- `GTIN` nunca em `attribute_combinations`;
- `EMPTY_GTIN_REASON` permanece em `item.attributes`;
- `GTIN` e `EMPTY_GTIN_REASON` nunca são enviados juntos;
- roteamento aplicado no Inspector, Readiness e imediatamente antes do POST `/items`.

## Versão

`enterprise-v5-sprint33-1-gtin-routing-hotfix`

## SQL

Não é necessário executar nova query.
