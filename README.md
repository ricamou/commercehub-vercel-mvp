# CommerceHub Enterprise V5 — Sprint 38

## Supplier Bulk Publication Pipeline

Executa para todos os anúncios importados o mesmo procedimento validado no primeiro produto:

1. Product Master;
2. Marketplace Inspector;
3. GTIN/identificadores;
4. Auto Completer;
5. Unified Payload;
6. Publication Readiness;
7. Publicação real, somente quando o produto estiver pronto.

## Segurança

O modo padrão é `prepare`.
Ele apenas analisa e registra os resultados.

O modo `publish` publica somente anúncios com:
- prontidão 100%;
- nenhuma pendência;
- nenhum atributo inválido;
- sem `external_id` anterior.

## Rotas

- `/supplier-bulk-publication?mode=prepare&limit=20`
- `/supplier-bulk-publication?mode=publish&limit=20`
- `/api/supplier-bulk-publication?mode=prepare&limit=20`

## Versão

`enterprise-v5-sprint38-supplier-bulk-publication-pipeline`

## Supabase

É necessário executar a query da Sprint 38.
