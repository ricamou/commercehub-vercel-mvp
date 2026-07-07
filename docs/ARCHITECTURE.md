# CommerceHub v0.5 — Arquitetura Técnica

## Objetivo

Reorganizar a base do projeto para suportar crescimento.

## Fluxo

```text
Fornecedor Simulado → CommerceHub Core → Mercado Livre
```

## Nova organização

### API

```text
app/routers/api/
```

Rotas voltadas para integrações e respostas JSON.

### Web

```text
app/routers/web/
```

Rotas do painel administrativo.

### Services

Regras de negócio.

### Connectors

Comunicação com sistemas externos.

### Templates

Interface web.

## Tokens

Na v0.5, os tokens continuam em variáveis de ambiente da Vercel.

## Próxima evolução

Na v0.6 ou v0.7, será necessário decidir onde armazenar tokens:

- Vercel Postgres;
- Supabase;
- Neon;
- Upstash;
- outro banco externo.
