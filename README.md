# Sprint 27.1 — Rules Engine Hotfix

Correções:

- remove o upsert incompatível com índice único baseado em COALESCE;
- usa SELECT + UPDATE/INSERT;
- trata corretamente brand e domain_id nulos;
- evita duplicar decisões a cada abertura da tela;
- uma falha ao salvar snapshot não derruba mais a página;
- mantém o Rules Engine funcionando mesmo se houver erro de persistência.

Não é necessário executar nova query.
Use as tabelas já criadas na Sprint 27.
