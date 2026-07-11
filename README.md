# CommerceHub Enterprise V5 — Sprint 34

## Unified Payload + Controlled Publish

Esta versão cria um único construtor de payload para:

- Marketplace Inspector;
- Prontidão para Publicação;
- publicação normal;
- tentativa controlada.

## Tentativa controlada

A tentativa somente é liberada quando:

- a única pendência é GTIN;
- não existe valor inválido;
- `EMPTY_GTIN_REASON` está em `item.attributes`;
- GTIN e EMPTY_GTIN_REASON não são enviados juntos;
- categoria e imagem estão presentes.

## Rotas

- `/api/unified-payload/listing/{listing_id}`
- `/api/publication-readiness/listing/{listing_id}/controlled-attempt`

## Versão

`enterprise-v5-sprint34-unified-payload-controlled-publish`

## Supabase

Não precisa criar nova query.
