# Integrações oficiais CommerceHub

## Mercado Livre

Status: funcional no sistema.

Recursos:
- OAuth
- Refresh token
- Consulta de conta
- Consulta de anúncios
- Consulta de pedidos
- Preview de anúncio
- Publicação preparada

## Shopee Open Platform

Status: preparado.

Recursos previstos:
- Autenticação de loja
- Produtos
- Pedidos
- Estoque
- Preço
- Webhooks quando disponíveis

Variáveis:
- SHOPEE_PARTNER_ID
- SHOPEE_PARTNER_KEY
- SHOPEE_SHOP_ID
- SHOPEE_ACCESS_TOKEN
- SHOPEE_REFRESH_TOKEN

## Amazon SP-API

Status: preparado.

Recursos previstos:
- Catálogo
- Pedidos
- Estoque
- Preço
- Relatórios

Variáveis:
- AMAZON_LWA_CLIENT_ID
- AMAZON_LWA_CLIENT_SECRET
- AMAZON_REFRESH_TOKEN
- AMAZON_MARKETPLACE_ID
- AMAZON_REGION

## Magalu Marketplace

Status: preparado.

Recursos previstos:
- Produtos
- Pedidos
- Webhooks
- SAC / perguntas
- Sincronização

Variáveis:
- MAGALU_CLIENT_ID
- MAGALU_CLIENT_SECRET
- MAGALU_ACCESS_TOKEN
- MAGALU_REFRESH_TOKEN
- MAGALU_SELLER_ID

## Fluxo definitivo

Supabase
→ Cadastro único de produto
→ IA / preço / estoque
→ Mercado Livre
→ Shopee
→ Amazon
→ Magalu
→ Pedidos
→ Relatórios
