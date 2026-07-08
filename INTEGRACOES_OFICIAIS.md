# Integrações oficiais pesquisadas

## Mercado Livre

Status no CommerceHub: funcional.

Uso atual:
- OAuth
- Refresh token
- Consulta de usuário
- Consulta de anúncios
- Consulta de pedidos
- Estrutura para publicar anúncio

## Shopee

Status no CommerceHub: preparado.

A Shopee Open Platform fornece documentação para produtos, pedidos, conta da loja, marketing e chat. Para ativar em produção é necessário acesso de desenvolvedor, Partner ID, Partner Key e autorização da loja.

Variáveis planejadas:
- SHOPEE_PARTNER_ID
- SHOPEE_PARTNER_KEY
- SHOPEE_SHOP_ID
- SHOPEE_REDIRECT_URI
- SHOPEE_ACCESS_TOKEN
- SHOPEE_REFRESH_TOKEN

## Amazon SP-API

Status no CommerceHub: preparado.

A Amazon Selling Partner API é REST e permite acesso a pedidos, envios, pagamentos, relatórios e outros dados. Para ativar é necessário registro como desenvolvedor SP-API, roles, app e autorização.

Variáveis planejadas:
- AMAZON_LWA_CLIENT_ID
- AMAZON_LWA_CLIENT_SECRET
- AMAZON_REFRESH_TOKEN
- AMAZON_AWS_ACCESS_KEY
- AMAZON_AWS_SECRET_KEY
- AMAZON_ROLE_ARN
- AMAZON_REGION
- AMAZON_MARKETPLACE_ID

## Magalu

Status no CommerceHub: preparado.

A documentação oficial da Magalu informa APIs de marketplace para produtos, pedidos, logística, SAC, perguntas e respostas, chat, análise financeira, sandbox e webhooks.

Variáveis planejadas:
- MAGALU_CLIENT_ID
- MAGALU_CLIENT_SECRET
- MAGALU_ACCESS_TOKEN
- MAGALU_REFRESH_TOKEN
- MAGALU_SELLER_ID

## Decisão de engenharia

O CommerceHub usará uma arquitetura de cadastro único:

Supabase
→ products
→ listing_payload
→ Mercado Livre / Shopee / Amazon / Magalu

Assim o produto é cadastrado uma vez e distribuído para múltiplos marketplaces.
