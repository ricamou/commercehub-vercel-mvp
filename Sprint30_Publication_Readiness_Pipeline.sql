-- ==========================================================
-- CommerceHub Sprint 30 - Publication Readiness Pipeline
-- Execute em uma NOVA QUERY no Supabase SQL Editor
-- ==========================================================

create table if not exists public.ml_publication_readiness (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  product_id uuid not null references public.products(id) on delete cascade,
  listing_id uuid references public.listings(id) on delete cascade,
  category_id text not null,
  status text not null default 'pending',
  readiness_score integer not null default 0,
  required_fields jsonb not null default '[]'::jsonb,
  completed_fields jsonb not null default '[]'::jsonb,
  missing_fields jsonb not null default '[]'::jsonb,
  invalid_fields jsonb not null default '[]'::jsonb,
  source_map jsonb not null default '{}'::jsonb,
  payload_preview jsonb not null default '{}'::jsonb,
  official_requirements jsonb not null default '{}'::jsonb,
  last_checked_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists uq_ml_publication_readiness
on public.ml_publication_readiness(product_id, category_id);

create index if not exists idx_ml_publication_readiness_status
on public.ml_publication_readiness(status, readiness_score desc);

drop trigger if exists trg_ml_publication_readiness_updated_at
on public.ml_publication_readiness;

create trigger trg_ml_publication_readiness_updated_at
before update on public.ml_publication_readiness
for each row execute function public.set_updated_at();

alter table public.ml_publication_readiness disable row level security;

select
  'publication_readiness_ready' as status,
  (select count(*) from public.ml_publication_readiness) as readiness_records;
