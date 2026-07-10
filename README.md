# CommerceHub Enterprise V5 - Sprint 15 Core Routes Fix

Correções desta versão:
- Substituição das chamadas inexistentes `db_select` por `store.select`.
- Substituição das chamadas inexistentes `db_insert` por `store.insert`.
- Correção do upsert de estoque usando a constraint composta `company_id,product_id`.
- Nova rota `/api/core/routes-check`.

Após o deploy, teste:
1. `/api/health`
2. `/api/install/verify`
3. `/api/core/routes-check`
4. `/products`
5. `/suppliers`
6. `/inventory`
7. `/logs`

Versão esperada:
`enterprise-v5-sprint15-core-routes-fix`
