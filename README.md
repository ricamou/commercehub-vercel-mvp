# CommerceHub Enterprise V5 — Sprint 20.1 Image Manager Enterprise

## Entregue
- Upload de imagem com diagnóstico detalhado de erro
- Galeria em cards
- Definir imagem principal
- Mover imagem para cima ou para baixo
- Copiar URL pública
- Abrir imagem
- Excluir do banco
- Excluir do Supabase Storage
- Atualização automática da imagem principal
- Remoção de caminhos locais inválidos
- Validação das imagens públicas
- Nenhuma publicação automática foi ativada

## Instalação
1. Suba os arquivos pelo GitHub Web.
2. Aguarde o deploy.
3. Confirme `/api/health`.
4. Faça login.
5. Abra `/upload-manager/sql` se ainda não executou a Sprint 20.
6. Abra o arquivo `sprint20_1_image_manager.sql` e execute em uma nova query.
7. Abra `/api/image-manager/status`.
8. Entre em Product Master → produto → Imagens.
9. Remova as imagens antigas inválidas.
10. Faça upload de uma imagem JPG, PNG ou WEBP.

## Versão
`enterprise-v5-sprint20-1-image-manager-enterprise`

## Observação
Em caso de falha no upload, o endpoint agora devolve JSON com:
- `error_type`
- `detail`
- `product_id`

Isso evita a tela genérica `Internal Server Error`.


## Hotfix 20.1.1

- Corrigido `NameError: name 're' is not defined`.
- Adicionado import defensivo em `s20_safe_filename`.
- Nenhum novo SQL é necessário.
- Versão esperada: `enterprise-v5-sprint20-1-1-image-manager-hotfix`.


## Hotfix 20.1.2 — Family Name

Correção aplicada ao payload de publicação do Mercado Livre:

- Adicionado o campo obrigatório `family_name`.
- O valor usa `seo_name`, depois `name`, e por último o título do anúncio.
- Limite automático de 60 caracteres.
- A URL pública da imagem permanece inalterada.
- Não é necessário executar novo SQL.
- Versão esperada: `enterprise-v5-sprint20-1-2-family-name-hotfix`.
