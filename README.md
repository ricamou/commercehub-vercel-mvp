# Sprint 27.3 — Missing Simulator Hotfix

Erro corrigido:

`NameError: name 's26_simulate_listing' is not defined`

A função de simulação da Sprint 26 não estava presente no arquivo final usado pela
Sprint 27. Esta versão restaura o simulador e inclui fallbacks para:

- s26_simulate_listing
- s26_build_payload
- s26_compare_payload
- s26_category_discovery

Não execute nova query no Supabase.
