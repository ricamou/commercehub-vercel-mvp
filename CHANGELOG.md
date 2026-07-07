# Changelog

## v0.5.0

### Added
- Reorganização profissional da estrutura de rotas.
- Novo pacote `app/routers/api`.
- Novo pacote `app/routers/web`.
- Serviço `TokenService`.
- Endpoint `/api/mercadolivre/token-status`.
- Endpoint `/api/mercadolivre/refresh-token`.
- Documentação de deploy.
- Documentação Mercado Livre.
- Tela Mercado Livre com bloco de orientação.

### Changed
- Separação mais clara entre rotas API e rotas Web.
- Dashboard atualizado para versão 0.5.0.
- README atualizado.

### Notes
- Tokens continuam via variáveis de ambiente da Vercel nesta versão.
- Persistência em banco externo fica planejada para versão futura.
