# CommerceHub v0.2

Sistema para integração:

**Fornecedor Simulado → CommerceHub → Mercado Livre**

Esta versão mantém o foco no fornecedor simulado e prepara a base para integração real com o Mercado Livre.

## O que há na v0.2

- Arquitetura profissional organizada.
- Fornecedor simulado mais realista.
- Cálculo de preço com:
  - margem de lucro;
  - comissão estimada do Mercado Livre;
  - custo fixo estimado;
  - arredondamento de preço.
- Preview do produto pronto para anúncio no Mercado Livre.
- Configuração centralizada.
- Logs básicos.
- Estrutura inicial de testes.
- Documentação técnica.

## Estrutura

```text
CommerceHub/
├── api/
│   └── main.py
├── app/
│   ├── core/
│   ├── connectors/
│   ├── routers/
│   ├── schemas/
│   └── services/
├── docs/
├── tests/
├── .env.example
├── .gitignore
├── requirements.txt
├── vercel.json
└── README.md
```

## Endpoints

Depois de publicar na Vercel:

```text
/
```

```text
/health
```

```text
/supplier/products
```

```text
/supplier/products/SUP-001
```

```text
/products
```

```text
/products/preview-ml
```

```text
/products/pricing/SUP-001
```

```text
/mercadolivre/status
```

## Importante

A v0.2 ainda **não publica produto real** no Mercado Livre.

Ela prepara os dados e a estrutura para a v0.3, onde iniciaremos autenticação OAuth do Mercado Livre.
