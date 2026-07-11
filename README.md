# CommerceHub Enterprise V5 — Sprint 32 Marketplace Auto Completer

## Objetivo

Consultar o que o Mercado Livre exige e preencher automaticamente os atributos usando os dados importados do fornecedor.

## Fluxo

1. Marketplace Inspector descobre os campos obrigatórios.
2. Auto Completer lê Product Master e payload bruto da Hayamax.
3. Aplica regras de mapeamento.
4. Valida o formato.
5. Salva os atributos do Mercado Livre.
6. Atualiza a Prontidão para Publicação.

## Mapeamentos iniciais

- marca → BRAND
- modelo/nome → MODEL
- ean/gtin/barcode/código de barras → GTIN
- cor → COLOR
- RGB → WITH_LIGHTS
- bluetooth → WITH_BLUETOOTH
- wireless → IS_WIRELESS
- peso e dimensões
- MPN/código do fabricante

## Instalação

1. Envie todos os arquivos pelo GitHub Web.
2. Aguarde o deploy.
3. Confirme `/api/health`.
4. Versão esperada:
   `enterprise-v5-sprint32-marketplace-auto-completer`
5. Execute `Sprint32_Marketplace_Auto_Completer.sql`.
6. Abra o anúncio.
7. Clique em `Auto Completar`.
8. Confira os campos preenchidos e os que ainda faltam.
