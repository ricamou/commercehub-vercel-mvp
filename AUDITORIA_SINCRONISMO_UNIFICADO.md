# Auditoria — Sincronismo Unificado

## Regra implantada

O `Product Master` é a única fonte de verdade para os dados de negócio do produto:

- título e descrição;
- categoria do Mercado Livre;
- preço de venda;
- estoque disponível;
- imagens;
- GTIN/EAN e marca;
- atributos gerais e atributos do marketplace.

O Listing permanece apenas como camada operacional de publicação. Configurações próprias do marketplace, como `listing_type_id`, `condition`, `currency_id` e identificadores externos, continuam no Listing.

## Gatilhos automáticos adicionados

- edição do Product Master;
- inclusão de imagem;
- inclusão ou atualização de atributo;
- criação ou atualização de rascunho do Listing;
- Discovery Engine e Workflow Engine, que já possuíam chamadas de sincronização.

## Proteções adicionadas

- o formulário de Listing não pode criar uma segunda versão de título, descrição, preço ou estoque;
- o payload enviado ao Mercado Livre é reconstruído usando Product Master + Inventory;
- após sincronização bem-sucedida, `products.sync_status` passa para `synchronized`;
- em falha após edição, o produto recebe `sync_status = error` e o erro é registrado em logs;
- a sincronização continua idempotente: repetir a operação não cria outro Listing.

## Testes automatizados

Arquivo: `tests/test_unified_sync.py`

Valida:

1. sobrescrita de dados divergentes do Listing pelos dados do Product Master;
2. sincronização de preço e estoque;
3. imagens, EAN, marca e atributos no snapshot;
4. atualização do status de sincronização;
5. geração do payload do Mercado Livre a partir da fonte oficial;
6. idempotência.

## Teste real ainda necessário

A atualização de um anúncio real depende das credenciais, token e conta Mercado Livre configurados na Vercel. Esse teste deve ser realizado no ambiente publicado após aplicar o ZIP.
