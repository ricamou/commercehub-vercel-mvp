# CommerceHub Enterprise V5 — Sprint 25 Marketplace Intelligence Engine

## Incluído

- base de conhecimento persistente por categoria e marca;
- armazenamento de erros reais do Mercado Livre;
- aprendizado automático das regras:
  - GTIN obrigatório;
  - GTIN inválido;
  - fluxo User Products com `family_name`;
- contador de ocorrências;
- nível de confiança;
- aplicação das regras antes da publicação;
- integração com Metadata Preflight;
- tela Marketplace Intelligence;
- histórico técnico de erros e payloads.

## Instalação

1. Envie os arquivos pelo GitHub Web.
2. Aguarde o deploy.
3. Abra `/api/health`.
4. Confirme:
   `enterprise-v5-sprint25-marketplace-intelligence-engine`
5. Execute `Sprint25_Marketplace_Intelligence.sql` em uma nova query no Supabase.
6. Abra `/api/marketplace-intelligence/category/MLB1714`.
7. Abra o anúncio e clique em `Marketplace Intelligence`.
8. Faça uma nova tentativa somente depois de corrigir os bloqueios.

## Observação

O sistema não cria GTIN e não substitui dados reais do fabricante. Ele aprende quando uma categoria ou combinação categoria/marca exige um GTIN verdadeiro.
