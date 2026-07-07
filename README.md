# CommerceHub v0.5

Sistema para integração:

**Fornecedor Simulado → CommerceHub → Mercado Livre**

## O que mudou na v0.5

Esta versão reorganiza o projeto para uma estrutura mais profissional e adiciona a primeira base para persistência de tokens.

## Novidades

- Reorganização geral da arquitetura.
- Criação de documentação de deploy.
- Criação de documentação Mercado Livre.
- Serviço central de tokens.
- Estrutura para renovação futura de tokens.
- Tela Mercado Livre melhorada.
- Endpoint `/api/mercadolivre/token-status`.
- Endpoint `/api/mercadolivre/refresh-token` estrutural.
- Mantido painel web.
- Mantido fornecedor simulado.
- Mantida base OAuth da v0.4.

## Estrutura

```text
CommerceHub/
├── api/
│   └── main.py
├── app/
│   ├── core/
│   ├── connectors/
│   │   ├── mercado_livre/
│   │   └── mock_supplier/
│   ├── routers/
│   │   ├── api/
│   │   └── web/
│   ├── schemas/
│   ├── services/
│   ├── static/
│   └── templates/
├── docs/
├── tests/
├── .env.example
├── .gitignore
├── CHANGELOG.md
├── requirements.txt
└── vercel.json
```

## Rotas Web

```text
/
```

```text
/dashboard
```

```text
/produtos
```

```text
/fornecedor
```

```text
/mercado-livre
```

```text
/mercadolivre/connect
```

```text
/mercadolivre/callback
```

## Rotas API

```text
/api/health
```

```text
/api/supplier/products
```

```text
/api/products
```

```text
/api/products/preview-ml
```

```text
/api/mercadolivre/status
```

```text
/api/mercadolivre/auth-url
```

```text
/api/mercadolivre/me
```

```text
/api/mercadolivre/token-status
```

```text
/api/mercadolivre/refresh-token
```

## Importante

A v0.5 ainda não publica anúncios reais. Ela prepara a base para a v0.6, onde vamos avançar para categorias/atributos e depois publicação controlada.
