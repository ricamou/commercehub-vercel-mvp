# CommerceHub v1 — Arquitetura Reorganizada

## Objetivo

Transformar o CommerceHub em uma base escalável para:

- fornecedores;
- marketplaces;
- produtos;
- anúncios;
- pedidos;
- estoque;
- precificação;
- IA.

## Estrutura modular

```text
app/
├── core/
├── connectors/
├── modules/
│   ├── core/
│   ├── marketplaces/
│   │   └── mercado_livre/
│   ├── suppliers/
│   │   └── mock_supplier/
│   ├── products/
│   ├── orders/
│   ├── pricing/
│   ├── inventory/
│   ├── ai/
│   └── reports/
├── routers/
├── services/
├── shared/
│   ├── database/
│   ├── security/
│   └── utils/
├── templates/
└── static/
```

## Fluxo alvo

```text
Fornecedor/API/XML/CSV
        ↓
CommerceHub
        ↓
Catálogo interno
        ↓
Anúncio Mercado Livre
        ↓
Cliente compra
        ↓
Pedido retorna via webhook
        ↓
Fornecedor processa envio
        ↓
Rastreio retorna ao marketplace
```

## Direção técnica

Esta versão ainda mantém compatibilidade com a base atual, mas prepara o caminho para migrar gradualmente os serviços para módulos independentes.
