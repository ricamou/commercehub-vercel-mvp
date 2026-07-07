# CommerceHub v0.2 — Arquitetura Técnica

## Objetivo

Criar a base profissional para um sistema que integre fornecedores ao Mercado Livre.

Fluxo atual:

```text
Fornecedor Simulado → CommerceHub → Mercado Livre
```

## Camadas

### Routers

Recebem as chamadas HTTP.

### Services

Contêm regras de negócio, como precificação e preparação dos produtos.

### Connectors

Representam sistemas externos ou simulados.

### Schemas

Definem os formatos dos dados.

## Conectores

### Mock Supplier

Fornecedor simulado com produtos, estoque, custo, medidas, marca, EAN e imagem.

### Mercado Livre

Ainda estrutural. Na v0.2 ele monta o payload de anúncio, mas não publica.

## Precificação

A v0.2 calcula o preço considerando:

- custo do produto;
- margem desejada;
- comissão estimada do Mercado Livre;
- custo fixo operacional;
- arredondamento comercial.

## Próximas versões

### v0.3

- Início da autenticação OAuth Mercado Livre.
- Variáveis de ambiente para credenciais.
- Callback de autenticação.

### v0.4

- Consulta de categorias.
- Validação de atributos.
- Preparação para publicação real.

### v0.5

- Publicação controlada de anúncio teste.
