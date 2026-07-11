# CommerceHub Enterprise V5 — Sprint 28 Marketplace Inspector

## Objetivo

Descobrir exatamente o que o Mercado Livre exige para um anúncio antes de ajustar o CommerceHub ou tentar publicar.

## O Inspector consulta

- categoria oficial;
- atributos oficiais;
- atributos condicionais;
- listing types disponíveis;
- payload atual do CommerceHub.

## O relatório mostra

- campos obrigatórios;
- campos condicionais;
- local correto: item ou variation;
- formato aceito;
- valores permitidos;
- endpoint oficial que comprovou a regra;
- campos faltantes;
- atributos desconhecidos enviados pelo CommerceHub.

## Instalação

1. Envie todos os arquivos pelo GitHub Web.
2. Aguarde o deploy.
3. Confirme `/api/health`.
4. Versão esperada:
   `enterprise-v5-sprint28-marketplace-inspector`
5. Execute `Sprint28_Marketplace_Inspector.sql` no Supabase.
6. Abra o anúncio.
7. Clique em `Marketplace Inspector`.
8. Use o relatório para fazer apenas os ajustes comprovados pelas APIs oficiais.
