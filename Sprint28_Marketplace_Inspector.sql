-- ==========================================================
-- CommerceHub Sprint 28 - Marketplace Inspector
-- Execute em uma NOVA QUERY no Supabase SQL Editor
-- ==========================================================

create table if not exists public.marketplace_inspector_runs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  marketplace text not null default 'mercado_livre',
  product_id uuid references public.products(id) on delete set null,
  listing_id uuid references public.listings(id) on delete set null,
  category_id text not null,
  status text not null default 'completed',
  category_snapshot jsonb not null default '{}'::jsonb,
  attributes_snapshot jsonb not null default '[]'::jsonb,
  conditional_snapshot jsonb not null default '{}'::jsonb,
  listing_types_snapshot jsonb not null default '[]'::jsonb,
  payload_snapshot jsonb not null default '{}'::jsonb,
  requirements_snapshot jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.marketplace_inspector_findings (
  id uuid primary key default uuid_generate_v4(),
  run_id uuid not null references public.marketplace_inspector_runs(id) on delete cascade,
  finding_type text not null,
  field_name text,
  required boolean not null default false,
  accepted_format text,
  accepted_values jsonb not null default '[]'::jsonb,
  location text,
  source_endpoint text,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_marketplace_inspector_runs_listing
  on public.marketplace_inspector_runs(listing_id, created_at desc);

create index if not exists idx_marketplace_inspector_findings_run
  on public.marketplace_inspector_findings(run_id, finding_type, field_name);

alter table public.marketplace_inspector_runs disable row level security;
alter table public.marketplace_inspector_findings disable row level security;

select
  'marketplace_inspector_ready' as status,
  (select count(*) from public.marketplace_inspector_runs) as runs,
  (select count(*) from public.marketplace_inspector_findings) as findings;
