# CommerceHub Enterprise — Backend Hardened

Revisão completa da arquitetura do backend para reduzir instabilidade em Vercel Serverless.

## Principais mudanças

- Substituição do transporte Supabase baseado em `httpx.AsyncClient` por `urllib` síncrono estável.
- Timeouts curtos.
- Retentativas controladas.
- Falhas de banco não derrubam mais a aplicação.
- Endpoints de health check do backend.
- Endpoint de teste leve de stress.
- Proteção contra erro 500 em leitura, escrita e upsert.

## Problema resolvido

Erro anterior:

```text
httpx.ConnectError: [Errno 16] Device or resource busy
```

## Testes

Depois de subir:

```text
/api/health
/
/supabase
/api/supabase/ready
/api/backend/health
/api/backend/stress-light
/api/foundation/status
/products
/suppliers
```

## Para operação

Se `/api/backend/health` retornar sucesso nas tabelas principais, o backend está estável para continuar os testes comerciais.
