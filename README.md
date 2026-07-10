# CommerceHub Enterprise V5 - Sprint 17 Universal Supplier Connector

## Entregue
- Conector universal para JSON, XML e CSV
- Hayamax como fornecedor de referência
- Cadastro e configuração da URL do catálogo
- Header opcional de autenticação
- Teste de conexão
- Pré-visualização normalizada
- Importação para `supplier_products`
- Criação/atualização do Catálogo Mestre (`products`)
- Atualização de estoque (`inventory`)
- Histórico em `sync_jobs` e `sync_logs`
- Importação demonstrativa Hayamax sem credenciais externas
- Proteção pelo login da Sprint 16

## Observação sobre Hayamax
A Hayamax informa publicamente que disponibiliza catálogo de dropshipping com preços,
imagens e descrições após ativação, e também possui histórico de integração por XML.
A URL e as credenciais reais precisam ser fornecidas ao revendedor pela Hayamax ou
parceiro de integração. Esta Sprint não inventa credenciais privadas.

## Instalação
1. Faça o deploy.
2. Confirme `/api/health`.
3. Entre no sistema.
4. Abra `/supplier-connector/sql`.
5. Copie o SQL e execute no Supabase SQL Editor.
6. Abra `/api/supplier-connector/status`.
7. Abra `/api/suppliers/hayamax/setup`.
8. Abra `/api/suppliers/hayamax/demo-import`.
9. Confira `/products`, `/inventory` e `/supplier-imports`.

## Versão esperada
`enterprise-v5-sprint17-universal-supplier-connector`

## Rotas principais
- `/supplier-connector`
- `/supplier-connector/sql`
- `/supplier-imports`
- `/api/supplier-connector/status`
- `/api/suppliers/hayamax/setup`
- `/api/suppliers/hayamax/demo-import`

## Limite GitHub Web
Pacote mantido abaixo de 100 arquivos.
