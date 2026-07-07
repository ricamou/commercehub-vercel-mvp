# CommerceHub v1 — Arquitetura Reorganizada

Sistema para integração:

**Fornecedor → CommerceHub → Marketplace → Cliente**

## Status atual

- Mercado Livre OAuth funcionando;
- Conta Mercado Livre conectada;
- Módulo de produtos/anúncios iniciado;
- Catálogo interno iniciado;
- Importador de fornecedores iniciado;
- Arquitetura modular criada.

## Rotas web principais

```text
/dashboard
/produtos
/catalogo/produtos
/fornecedor
/fornecedores
/mercado-livre
/anuncios
/arquitetura
```

## Rotas API principais

```text
/api/health
/api/mercadolivre/me
/api/mercadolivre/categories/search?q=suporte celular
/api/catalog/products
/api/admin/suppliers
/api/admin/suppliers/mock/preview-import
/api/admin/suppliers/mock/import
```

## Próxima etapa recomendada

Migrar o armazenamento temporário `/tmp` para banco persistente externo.
