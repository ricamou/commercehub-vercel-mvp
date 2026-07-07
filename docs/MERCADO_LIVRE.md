# Integração Mercado Livre

## v0.5

A integração atual contém:

- geração da URL de autorização;
- callback OAuth;
- troca do `code` por token;
- leitura de tokens por variável de ambiente;
- consulta `/users/me`;
- refresh token estrutural.

## Redirect URI

Use:

```text
https://commercehub-vercel-mvp.vercel.app/mercadolivre/callback
```

## Próximas etapas

- persistir tokens em banco externo;
- renovar token automaticamente;
- consultar categorias;
- validar atributos obrigatórios;
- publicar produto teste.
