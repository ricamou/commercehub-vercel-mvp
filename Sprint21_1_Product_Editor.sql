-- ==========================================================
-- CommerceHub Sprint 21.1 - Product Editor
-- Execute em uma NOVA QUERY no Supabase SQL Editor
-- ==========================================================

alter table public.products
  add column if not exists model text,
  add column if not exists ml_category_id text;

create index if not exists idx_products_ml_category
  on public.products(company_id, ml_category_id);

-- Preenche a categoria do Product Master usando os rascunhos já existentes.
update public.products p
set ml_category_id = l.category_id
from public.listings l
where l.product_id = p.id
  and l.marketplace = 'mercado_livre'
  and l.category_id is not null
  and (p.ml_category_id is null or p.ml_category_id = '');

select
  'product_editor_ready' as status,
  count(*) as products,
  count(*) filter (where model is not null and model <> '') as products_with_model,
  count(*) filter (where ml_category_id is not null and ml_category_id <> '') as products_with_ml_category
from public.products;
