# CommerceHub Enterprise — No Mocks Ready

Versão pronta para operar com Supabase como fonte principal.

## O que foi corrigido

- Telas principais priorizam dados reais do Supabase.
- Produtos, fornecedores e estoque deixam de depender de mocks quando Supabase está conectado.
- Endpoints de preparação automática do banco.
- Endpoint de criação de produto real de teste.
- Preview comercial para Mercado Livre.
- Fluxo pronto para: Supabase → Produto → Estoque → Preview → Marketplace.

## Testes

- `/api/health`
- `/api/foundation/status`
- `/api/setup/ensure-seed`
- `/api/commercial-test/create-product`
- `/api/commercial-test/check`
- `/products`
- `/suppliers`
- `/inventory`
- `/api/commercial-test/preview?category_id=MLBXXXX`

## Uso

Suba no GitHub Web e aguarde a Vercel.

Depois teste:

1. `/api/foundation/status`
2. `/api/setup/ensure-seed`
3. `/api/commercial-test/create-product`
4. `/products`
5. `/suppliers`
6. `/inventory`
7. `/api/commercial-test/preview?category_id=MLBXXXX`
