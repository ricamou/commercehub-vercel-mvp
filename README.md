# CommerceHub Enterprise V5 — Sprint 33 GTIN Intelligence Engine

## Objetivo

Ampliar a descoberta de GTIN usando:

1. fontes internas já implementadas;
2. consultas ao catálogo do Mercado Livre;
3. comparação por marca, modelo, nome, MPN e SKU;
4. validação matemática do GTIN;
5. score mínimo de 80% antes de salvar automaticamente.

## Segurança

O sistema não salva o primeiro resultado encontrado.
Ele só seleciona automaticamente quando:

- o GTIN possui formato e dígito verificador válidos;
- a correspondência entre produto importado e catálogo é de pelo menos 80%.

Resultados abaixo desse nível aparecem apenas como candidatos.

## Instalação

1. Envie todos os arquivos pelo GitHub Web.
2. Aguarde o deploy.
3. Confirme `/api/health`.
4. Versão esperada:
   `enterprise-v5-sprint33-gtin-intelligence-engine`
5. Execute a query da Sprint 33 no Supabase.
6. Abra o anúncio.
7. Clique em `GTIN Intelligence`.
8. Depois clique em `Atualizar Prontidão`.
