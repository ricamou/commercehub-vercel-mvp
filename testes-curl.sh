# CommerceHub QA - comandos curl

BASE="https://commercehub-vercel-mvp.vercel.app"


echo "\n### Health"
curl -s "$BASE/api/health"

echo "\n### Dashboard"
curl -s "$BASE/dashboard"

echo "\n### Enterprise Final"
curl -s "$BASE/enterprise-final"

echo "\n### Sprint 1"
curl -s "$BASE/sprint1"

echo "\n### Sprint 2"
curl -s "$BASE/sprint2"

echo "\n### Sprint 3"
curl -s "$BASE/sprint3"

echo "\n### Produtos API"
curl -s "$BASE/api/produtos"

echo "\n### Fornecedores API"
curl -s "$BASE/api/fornecedores"

echo "\n### Connectors Status"
curl -s "$BASE/api/connectors/status"

echo "\n### Import Summary Mock"
curl -s "$BASE/api/import/summary/mock"

echo "\n### Sync Compare"
curl -s "$BASE/api/sync/compare"

echo "\n### Sync Marketplace Payload"
curl -s "$BASE/api/sync/marketplace-payload"

echo "\n### Pricing Report"
curl -s "$BASE/api/pricing/report"

echo "\n### AI Report"
curl -s "$BASE/api/ai/report"

echo "\n### Preview Anúncio"
curl -s "$BASE/api/anuncios/preview/SUP-001?category_id=MLBXXXX"

echo "\n### Mercado Livre Status"
curl -s "$BASE/api/mercadolivre/status"

echo "\n### Database Status"
curl -s "$BASE/api/database/status"

echo "\n### POST Connector Parse JSON"
curl -s -X POST "$BASE/api/connectors/parse/json" \
  -H "Content-Type: application/json" \
  -d '{"payload":{"sku":"TEST-001","name":"Produto Teste","brand":"Marca Teste","ean":"7890000000000","category":"Teste","description":"Produto de teste","cost_price":20,"stock":10}}'

echo "\n### POST Sync Run Demo"
curl -s -X POST "$BASE/api/sync/run-demo" -H "Content-Type: application/json" -d '{}'
