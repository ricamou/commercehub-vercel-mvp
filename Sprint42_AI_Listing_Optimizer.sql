-- ==========================================================
-- CommerceHub Sprint 42 - AI Listing Optimizer
-- Execute em uma NOVA QUERY no Supabase SQL Editor
-- ==========================================================

create table if not exists public.marketplace_listing_enrichments (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  marketplace text not null default 'mercado_livre',
  listing_id uuid references public.listings(id) on delete cascade,
  product_id uuid references public.products(id) on delete cascade,
  external_item_id text not null,
  source_snapshot jsonb not null default '{}'::jsonb,
  optimized_title text,
  optimized_description text,
  optimized_pictures jsonb not null default '[]'::jsonb,
  optimized_attributes jsonb not null default '[]'::jsonb,
  faq jsonb not null default '[]'::jsonb,
  expected_score integer,
  status text not null default 'preview',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_marketplace_listing_enrichments_item
on public.marketplace_listing_enrichments(external_item_id, created_at desc);

create table if not exists public.marketplace_optimization_action_log (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  optimization_job_id uuid references public.marketplace_optimization_jobs(id) on delete set null,
  external_item_id text not null,
  action text not null,
  status text not null,
  request_payload jsonb not null default '{}'::jsonb,
  response_payload jsonb not null default '{}'::jsonb,
  error_message text,
  created_at timestamptz not null default now()
);

create index if not exists idx_marketplace_optimization_action_log_item
on public.marketplace_optimization_action_log(external_item_id, created_at desc);

drop trigger if exists trg_marketplace_listing_enrichments_updated_at
on public.marketplace_listing_enrichments;

create trigger trg_marketplace_listing_enrichments_updated_at
before update on public.marketplace_listing_enrichments
for each row execute function public.set_updated_at();

alter table public.marketplace_listing_enrichments disable row level security;
alter table public.marketplace_optimization_action_log disable row level security;

select
  'ai_listing_optimizer_ready' as status,
  (select count(*) from public.marketplace_listing_enrichments) as enrichments,
  (select count(*) from public.marketplace_optimization_action_log) as action_logs;
