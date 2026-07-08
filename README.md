# CommerceHub Programa Pronto v1

Versão fechada do programa, sem novos módulos e sem expansão de escopo.

## Objetivo

Entregar o sistema funcionando com:

- Dashboard
- Produtos
- Fornecedores
- Anúncios
- Relatórios
- AI Engine
- Mercado Livre OAuth
- Refresh de token
- Preview de anúncio
- Testes finais

## Teste final

Depois de subir na Vercel:

- /api/health
- /api/final-check
- /mercado-livre
- /api/mercadolivre/status
- /api/mercadolivre/me
- /api/produtos
- /api/anuncios/preview/SUP-001?category_id=MLBXXXX

## Observação

O sistema funciona com tokens nas Environment Variables da Vercel.
Supabase continua opcional para persistência.
