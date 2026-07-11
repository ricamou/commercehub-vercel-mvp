# CommerceHub Enterprise V5 — Sprint 29 Marketplace Knowledge Engine

## Objetivo

Consolidar em uma base persistente as regras oficiais descobertas pelo Marketplace Inspector.

## O que esta versão faz

- cria perfil por categoria + marca + domínio;
- salva fingerprint das regras;
- consolida atributos obrigatórios e condicionais;
- registra local correto: item ou variation;
- registra formato e valores aceitos;
- consolida política de GTIN;
- diferencia presença de EMPTY_GTIN_REASON de substituição efetiva do GTIN;
- gera recomendações comprovadas;
- preserva as fontes oficiais consultadas.

## Instalação

1. Envie todos os arquivos pelo GitHub Web.
2. Aguarde o deploy.
3. Confirme `/api/health`.
4. Versão esperada:
   `enterprise-v5-sprint29-marketplace-knowledge-engine`
5. Execute `Sprint29_Marketplace_Knowledge_Engine.sql`.
6. Abra o anúncio.
7. Clique em `Knowledge Engine`.
8. Use apenas as recomendações comprovadas antes de ajustar o CommerceHub.
