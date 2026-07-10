# CommerceHub Enterprise V5 — Sprint 20 Upload Manager

## Entregue
- Upload de JPG, PNG e WEBP pelo navegador
- Armazenamento no Supabase Storage
- Bucket público `product-images`
- Geração automática de URL pública
- Gravação no Product Master
- Definição de imagem principal
- Validação de URL pública
- Bloqueio de caminhos locais `C:\Users\...`
- Envio das URLs públicas ao Mercado Livre
- Upload Manager em `/upload-manager`
- Dois modos: `Publicar agora` e `Publicação automática`
- Automação global desligada por padrão
- Automação por anúncio e executor controlado

## Instalação
1. Envie todos os arquivos no GitHub Web.
2. Aguarde o deploy.
3. Confirme `/api/health`.
4. Faça login.
5. Abra `/upload-manager/sql`.
6. Copie o SQL.
7. Supabase → SQL Editor → New query → cole → Run.
8. Abra `/api/upload-manager/status`.
9. Abra um produto → Imagens.
10. Selecione uma imagem JPG/PNG/WEBP e envie.
11. Abra a URL pública gerada.
12. Volte ao anúncio e publique.

## Versão esperada
`enterprise-v5-sprint20-upload-manager-supabase-storage`

## Variáveis
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_STORAGE_BUCKET=product-images`
- `MAX_IMAGE_MB=5`

## Modos de publicação
### Manual
O usuário revisa e clica em `Publicar agora`.

### Automático
1. Ative globalmente em `/listing-automation`.
2. Ative no anúncio específico.
3. Execute `/api/listing-engine/automation/run` pelo botão da tela.
4. Apenas anúncios válidos são publicados.

A automação agendada contínua poderá ser ligada a um cron em sprint posterior.

## Limite GitHub Web
Pacote mantido abaixo de 100 arquivos.
