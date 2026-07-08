# CommerceHub Comercial Completo v1

Versão consolidada para uso comercial inicial.

## Base do sistema

- Supabase como banco definitivo
- Cadastro único de produtos
- Empresas
- Usuários
- Fornecedores
- Produtos
- Estoque
- Pedidos
- Anúncios
- OAuth Tokens
- Logs
- AI History
- Filas
- Webhooks
- Sync Jobs
- Mercado Livre funcional
- Shopee preparado
- Amazon SP-API preparado
- Magalu preparado

## Primeiro teste real sem API de fornecedor

1. Rodar `supabase_schema.sql` no Supabase.
2. Configurar `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` na Vercel.
3. Acessar `/api/foundation/seed`.
4. Cadastrar um produto via `POST /api/products`.
5. Gerar preview em `/api/listings/preview/{product_id}`.
6. Publicar no Mercado Livre quando o payload estiver validado.

## Testes principais

- `/api/health`
- `/api/foundation/status`
- `/foundation`
- `/api/foundation/seed`
- `/products`
- `/suppliers`
- `/inventory`
- `/orders`
- `/listings`
- `/logs`
- `/queue`
- `/sync`
- `/mercado-livre`
- `/api/mercadolivre/me`
- `/api/ml/items`
- `/api/ml/orders`

## Observação

A versão está pronta para operação controlada. Para Shopee, Amazon e Magalu, será necessário inserir as credenciais oficiais de cada plataforma e ativar os endpoints reais conforme aprovação de cada programa de desenvolvedor.
