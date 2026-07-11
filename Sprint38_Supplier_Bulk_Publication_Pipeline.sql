-- ==========================================================
-- CommerceHub Sprint 38 - Supplier Bulk Publication Pipeline
-- Execute em uma NOVA QUERY no Supabase SQL Editor
-- ==========================================================

create table if not exists public.bulk_publication_runs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  mode text not null default 'prepare',
  supplier_filter text,
  status text not null default 'running',
  requested_limit integer not null default 20,
  processed_count integer not null default 0,
  ready_count integer not null default 0,
  blocked_count integer not null default 0,
  published_count integer not null default 0,
  failed_count integer not null default 0,
  summary jsonb not null default '{}'::jsonb,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists idx_bulk_publication_runs_created_at
on public.bulk_publication_runs(created_at desc);

create table if not exists public.bulk_publication_items (
  id uuid primary key default uuid_generate_v4(),
  run_id uuid not null references public.bulk_publication_runs(id) on delete cascade,
  company_id uuid references public.companies(id) on delete cascade,
  listing_id uuid references public.listings(id) on delete set null,
  product_id uuid references public.products(id) on delete set null,
  supplier text,
  category_id text,
  readiness_status text,
  readiness_score integer not null default 0,
  processing_status text not null default 'pending',
  marketplace_item_id text,
  error_code text,
  error_message text,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_bulk_publication_items_run
on public.bulk_publication_items(run_id, processing_status);

create index if not exists idx_bulk_publication_items_listing
on public.bulk_publication_items(listing_id, created_at desc);

drop trigger if exists trg_bulk_publication_items_updated_at
on public.bulk_publication_items;

create trigger trg_bulk_publication_items_updated_at
before update on public.bulk_publication_items
for each row execute function public.set_updated_at();

alter table public.bulk_publication_runs disable row level security;
alter table public.bulk_publication_items disable row level security;

select
  'supplier_bulk_publication_pipeline_ready' as status,
  (select count(*) from public.bulk_publication_runs) as runs,
  (select count(*) from public.bulk_publication_items) as items;
