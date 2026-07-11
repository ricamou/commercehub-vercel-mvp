# CommerceHub Enterprise V5 — Sprint 35

## Conditional Identifier Logic

Correção principal:

- `GTIN` e `EMPTY_GTIN_REASON` não são tratados como dois campos obrigatórios simultâneos;
- GTIN válido satisfaz a exigência e remove a pendência de `EMPTY_GTIN_REASON`;
- motivo de ausência satisfaz a alternativa quando o contexto permitir;
- GTIN e motivo juntos continuam bloqueados;
- a tentativa controlada é liberada quando o payload está completo e sem conflito.

## Caso atual

O código `7908429311635` passa na validação matemática de EAN-13 e está em `item.attributes`.

## Versão

`enterprise-v5-sprint35-conditional-identifier-logic`

## Supabase

Não é necessário criar nova query.
