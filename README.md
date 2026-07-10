# CommerceHub Enterprise V5 — Sprint 21.2 Intelligent Attribute Payload

## Correção principal

O CommerceHub não envia mais:

```json
{"id":"GTIN","value_name":"EMPTY_GTIN_REASON"}
```

Agora:

- valida o GTIN matematicamente;
- aceita GTIN de 8, 12, 13 ou 14 dígitos;
- remove GTIN inválido do payload;
- trata `EMPTY_GTIN_REASON` como atributo separado;
- usa `value_id` quando o Mercado Livre fornece valores permitidos;
- impede o envio quando existem atributos obrigatórios ou inválidos;
- mantém GTIN e EMPTY_GTIN_REASON mutuamente exclusivos.

## Instalação

1. Envie todos os arquivos pelo GitHub Web.
2. Aguarde o deploy.
3. Confirme `/api/health`.
4. Versão esperada: `enterprise-v5-sprint21-2-intelligent-attribute-payload`.
5. Não é necessário executar novo SQL.
6. Abra os Atributos Inteligentes.
7. No campo GTIN:
   - coloque um GTIN verdadeiro; ou
   - deixe vazio.
8. Se o produto não tiver GTIN, preencha `EMPTY_GTIN_REASON` com uma opção permitida.
9. Valide.
10. Publique somente quando `valid=true`.

## Observação

Um código com dígito verificador correto ainda precisa pertencer realmente ao produto.
