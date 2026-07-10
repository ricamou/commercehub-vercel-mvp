# CommerceHub Enterprise V5 - Sprint 16 Enterprise Auth

## Incluído
- Login real contra `users_app`
- Verificação SHA-256 compatível com o seed atual
- Token JWT HS256 sem biblioteca adicional
- Cookie HttpOnly, Secure e SameSite=Lax
- Logout
- Perfil
- Papéis: admin, operator e viewer
- Middleware protegendo páginas e APIs
- Rotas `/api/auth/status` e `/api/auth/admin-check`
- Logs de login e logout

## Variável obrigatória na Vercel
Crie:

`SESSION_SECRET`

Use uma chave longa, privada e aleatória.

Também estão disponíveis:
- `AUTH_REQUIRED=true`
- `SESSION_HOURS=12`
- `COOKIE_SECURE=true`

## Teste após o deploy
1. `/api/health`
2. `/login`
3. Entre com:
   - Email: `admin@commercehub.local`
   - Senha: `admin123`
4. `/profile`
5. `/api/auth/status`
6. `/api/auth/admin-check`
7. `/logout`

## Versão esperada
`enterprise-v5-sprint16-enterprise-auth`

## Total de arquivos
Mantido abaixo do limite de 100 arquivos do GitHub Web.
