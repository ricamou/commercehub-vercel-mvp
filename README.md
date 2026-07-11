# Sprint 31.1 — Product Master Hotfix

Correção aplicada:

- remove um bloco do GTIN Resolver que foi inserido indevidamente dentro da rota `/product-master`;
- elimina referências inexistentes a `category_id`, `product_id`, `vals` e `resolver_html`;
- restaura a listagem normal do Product Master;
- mantém o GTIN Discovery Engine da Sprint 31.

Não é necessário executar nova query no Supabase.
