# CommerceHub Enterprise V5 — Sprint 30 Publication Readiness Pipeline

## Objetivo

Garantir que todo produto importado tenha todas as informações exigidas pelo Mercado Livre antes de publicar.

## Fluxo

1. Produto importado do fornecedor.
2. Categoria do Mercado Livre definida.
3. Marketplace Inspector consulta requisitos oficiais.
4. CommerceHub compara requisitos com Product Master e atributos.
5. Dados disponíveis são preenchidos automaticamente.
6. Campos faltantes ou inválidos são exibidos.
7. Botão Publicar só envia quando o status estiver PRONTO.

## Recursos

- score de prontidão;
- campos obrigatórios;
- campos preenchidos;
- campos faltantes;
- campos inválidos;
- origem de cada valor;
- payload preparado;
- bloqueio de publicação incompleta;
- publicação real quando aprovado.

## Instalação

1. Envie todos os arquivos pelo GitHub Web.
2. Aguarde o deploy.
3. Confirme `/api/health`.
4. Versão esperada:
   `enterprise-v5-sprint30-publication-readiness-pipeline`
5. Execute `Sprint30_Publication_Readiness_Pipeline.sql`.
6. Abra o anúncio.
7. Clique em `Prontidão para Publicação`.
