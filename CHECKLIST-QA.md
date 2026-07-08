# CommerceHub — Roteiro de Testes QA

Base URL:
https://commercehub-vercel-mvp.vercel.app

## Ordem de teste

1. Health
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/api/health
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.

2. Dashboard
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/dashboard
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.

3. Enterprise Final
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/enterprise-final
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.

4. Sprint 1
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/sprint1
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.

5. Sprint 2
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/sprint2
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.

6. Sprint 3
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/sprint3
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.

7. Produtos API
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/api/produtos
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.

8. Fornecedores API
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/api/fornecedores
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.

9. Connectors Status
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/api/connectors/status
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.

10. Import Summary Mock
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/api/import/summary/mock
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.

11. Sync Compare
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/api/sync/compare
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.

12. Sync Marketplace Payload
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/api/sync/marketplace-payload
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.

13. Pricing Report
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/api/pricing/report
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.

14. AI Report
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/api/ai/report
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.

15. Preview Anúncio
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/api/anuncios/preview/SUP-001?category_id=MLBXXXX
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.

16. Mercado Livre Status
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/api/mercadolivre/status
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.

17. Database Status
   - Método: GET
   - URL: https://commercehub-vercel-mvp.vercel.app/api/database/status
   - Esperado: abrir sem erro 500 e retornar página ou JSON válido.


## Teste POST — JSON

URL:
https://commercehub-vercel-mvp.vercel.app/api/connectors/parse/json

Método:
POST

Body JSON:
{
  "payload": {
    "sku": "TEST-001",
    "name": "Produto Teste",
    "brand": "Marca Teste",
    "ean": "7890000000000",
    "category": "Teste",
    "description": "Produto de teste",
    "cost_price": 20,
    "stock": 10
  }
}

Esperado:
success true, count 1, produto normalizado.

## Teste POST — Sync Demo

URL:
https://commercehub-vercel-mvp.vercel.app/api/sync/run-demo

Método:
POST

Body:
{}

Esperado:
success true e actions completed.

## Teste real Mercado Livre

Só avance para publicação real depois de:
1. /api/mercadolivre/status mostrar access_token true.
2. /api/mercadolivre/me retornar success true.
3. /api/anuncios/preview/SUP-001?category_id=MLBXXXX retornar payload correto.
