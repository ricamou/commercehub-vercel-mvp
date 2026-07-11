# CommerceHub Enterprise V5 — Sprint 37 Seller Eligibility Inspector

## Objetivo

Aprofundar o erro `seller.unable_to_list` usando verificações específicas para:

- usuário autenticado;
- categoria do anúncio;
- tipo de anúncio escolhido;
- disponibilidade do listing type para o vendedor;
- existência de anúncios anteriores;
- tags do perfil, incluindo `user_product_seller`;
- provável onboarding do primeiro anúncio.

## Rotas

- `/seller-eligibility/listing/{listing_id}`
- `/api/seller-eligibility/listing/{listing_id}`

## Interpretação

A API pública pode não expor o motivo interno exato do bloqueio. Quando isso ocorrer,
o sistema separa:

- bloqueio comprovado;
- provável onboarding do primeiro anúncio;
- restrição não exposta pela API pública.

## Versão

`enterprise-v5-sprint37-seller-eligibility-inspector`

## Supabase

Não é necessário criar nova query.
