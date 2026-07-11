-- ==========================================================
-- CommerceHub Sprint 33 - GTIN Intelligence Engine
-- Execute em uma NOVA QUERY no Supabase SQL Editor
-- ==========================================================

create table if not exists public.gtin_intelligence_runs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  product_id uuid not null references public.products(id) on delete cascade,
  listing_id uuid references public.listings(id) on delete set null,
  category_id text,
  status text not null default 'pending',
  query_terms jsonb not null default '[]'::jsonb,
  internal_result jsonb not null default '{}'::jsonb,
  ml_catalog_result jsonb not null default '{}'::jsonb,
  candidates jsonb not null default '[]'::jsonb,
  selected_candidate jsonb not null default '{}'::jsonb,
  confidence numeric(5,2) not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists idx_gtin_intelligence_runs_product
on public.gtin_intelligence_runs(product_id, created_at desc);

create table if not exists public.gtin_intelligence_candidates (
  id uuid primary key default uuid_generate_v4(),
  run_id uuid not null references public.gtin_intelligence_runs(id) on delete cascade,
  provider text not null,
  gtin text,
  brand text,
  model text,
  title text,
  catalog_product_id text,
  match_score numeric(5,2) not null default 0,
  valid_gtin boolean not null default false,
  selected boolean not null default false,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_gtin_intelligence_candidates_run
on public.gtin_intelligence_candidates(run_id, match_score desc);

alter table public.gtin_intelligence_runs disable row level security;
alter table public.gtin_intelligence_candidates disable row level security;

select
  'gtin_intelligence_engine_ready' as status,
  (select count(*) from public.gtin_intelligence_runs) as runs,
  (select count(*) from public.gtin_intelligence_candidates) as candidates;
