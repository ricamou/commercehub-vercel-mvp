-- ==========================================================
-- CommerceHub Sprint 41 - Marketplace Quality Engine
-- Execute em uma NOVA QUERY no Supabase SQL Editor
-- ==========================================================

create table if not exists public.marketplace_quality_reports (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  marketplace text not null default 'mercado_livre',
  listing_id uuid references public.listings(id) on delete cascade,
  product_id uuid references public.products(id) on delete cascade,
  external_item_id text not null,
  score integer not null default 0,
  level text not null default 'basic',
  photos_count integer not null default 0,
  attributes_filled integer not null default 0,
  attributes_total integer not null default 0,
  description_present boolean not null default false,
  warranty_present boolean not null default false,
  free_shipping boolean not null default false,
  installments_ready boolean not null default false,
  wholesale_ready boolean not null default false,
  regulatory_ready boolean not null default false,
  objectives jsonb not null default '[]'::jsonb,
  recommendations jsonb not null default '[]'::jsonb,
  marketplace_payload jsonb not null default '{}'::jsonb,
  analyzed_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists idx_marketplace_quality_reports_item
on public.marketplace_quality_reports(external_item_id, analyzed_at desc);

create index if not exists idx_marketplace_quality_reports_listing
on public.marketplace_quality_reports(listing_id, analyzed_at desc);

create table if not exists public.marketplace_optimization_jobs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  marketplace text not null default 'mercado_livre',
  listing_id uuid references public.listings(id) on delete cascade,
  product_id uuid references public.products(id) on delete cascade,
  external_item_id text not null,
  status text not null default 'pending',
  actions jsonb not null default '[]'::jsonb,
  applied_actions jsonb not null default '[]'::jsonb,
  failed_actions jsonb not null default '[]'::jsonb,
  before_score integer,
  after_score integer,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  finished_at timestamptz
);

create index if not exists idx_marketplace_optimization_jobs_status
on public.marketplace_optimization_jobs(status, created_at desc);

drop trigger if exists trg_marketplace_optimization_jobs_updated_at
on public.marketplace_optimization_jobs;

create trigger trg_marketplace_optimization_jobs_updated_at
before update on public.marketplace_optimization_jobs
for each row execute function public.set_updated_at();

alter table public.marketplace_quality_reports disable row level security;
alter table public.marketplace_optimization_jobs disable row level security;

select
  'marketplace_quality_engine_ready' as status,
  (select count(*) from public.marketplace_quality_reports) as reports,
  (select count(*) from public.marketplace_optimization_jobs) as jobs;
