# CommerceHub Enterprise V5 — Sprint 31 GTIN Discovery Engine

## Objetivo

Descobrir e preencher automaticamente o GTIN antes da publicação.

## Fontes consultadas nesta versão

1. Product Master (`ean` ou `gtin`);
2. payload bruto do fornecedor/importação;
3. atributos do marketplace já salvos;
4. catálogo interno aprendido do CommerceHub.

## O que o sistema faz quando encontra

- valida o dígito verificador;
- identifica o tipo: GTIN-8, UPC-A, EAN-13 ou GTIN-14;
- salva no catálogo interno;
- tenta atualizar o Product Master;
- grava o atributo GTIN do Mercado Livre;
- atualiza a Prontidão para Publicação.

## Quando não encontra

O produto continua BLOQUEADO e a tela mostra todas as fontes verificadas.

## Instalação

1. Envie todos os arquivos pelo GitHub Web.
2. Aguarde o deploy.
3. Confirme `/api/health`.
4. Versão esperada:
   `enterprise-v5-sprint31-gtin-discovery-engine`
5. Execute `Sprint31_GTIN_Discovery_Engine.sql`.
6. Abra o anúncio.
7. Clique em `Descobrir GTIN`.
8. Depois clique em `Atualizar Prontidão`.
