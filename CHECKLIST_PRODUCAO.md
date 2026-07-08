# Checklist de produção CommerceHub

## 1. Banco

- [ ] Criar projeto Supabase
- [ ] Rodar `supabase_schema.sql`
- [ ] Configurar `SUPABASE_URL`
- [ ] Configurar `SUPABASE_SERVICE_ROLE_KEY`
- [ ] Redeploy na Vercel
- [ ] Testar `/api/foundation/status`
- [ ] Confirmar `mode: supabase`

## 2. Mercado Livre

- [ ] Confirmar `/mercado-livre` conectado
- [ ] Testar `/api/mercadolivre/me`
- [ ] Testar `/api/ml/items`
- [ ] Testar `/api/ml/orders`
- [ ] Salvar token no Supabase via OAuth callback ou seed

## 3. Produto real sem fornecedor API

- [ ] Criar fornecedor manual
- [ ] Criar produto real
- [ ] Criar movimento de estoque
- [ ] Gerar preview de anúncio
- [ ] Validar categoria real
- [ ] Publicar anúncio de teste

## 4. Operação

- [ ] Receber webhook
- [ ] Salvar pedido no banco
- [ ] Atualizar estoque
- [ ] Registrar log
- [ ] Criar sync job
- [ ] Processar fila

## 5. Expansão

- [ ] Shopee: solicitar acesso developer
- [ ] Amazon: registrar SP-API
- [ ] Magalu: criar app e chaves
