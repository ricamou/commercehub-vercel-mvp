-- ==========================================================
-- CommerceHub Sprint 31 - GTIN Discovery Engine
-- Execute em uma NOVA QUERY no Supabase SQL Editor
-- ==========================================================

create table if not exists public.gtin_catalog (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  product_id uuid references public.products(id) on delete cascade,
  brand text,
  model text,
  mpn text,
  sku text,
  gtin text not null,
  gtin_type text,
  source text not null,
  confidence numeric(5,2) not null default 100,
  source_payload jsonb not null default '{}'::jsonb,
  verified boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists uq_gtin_catalog_product_gtin
on public.gtin_catalog(product_id, gtin);

create index if not exists idx_gtin_catalog_lookup
on public.gtin_catalog(brand, model, mpn, sku, confidence desc);

create table if not exists public.gtin_lookup_history (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  product_id uuid not null references public.products(id) on delete cascade,
  listing_id uuid references public.listings(id) on delete set null,
  provider text not null,
  query_data jsonb not null default '{}'::jsonb,
  result_data jsonb not null default '{}'::jsonb,
  found boolean not null default false,
  gtin text,
  confidence numeric(5,2) not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists idx_gtin_lookup_history_product
on public.gtin_lookup_history(product_id, created_at desc);

create table if not exists public.gtin_sources (
  id uuid primary key default uuid_generate_v4(),
  provider text not null unique,
  priority integer not null,
  enabled boolean not null default true,
  source_type text not null default 'internal',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into public.gtin_sources(provider, priority, enabled, source_type)
values
  ('product_master', 1, true, 'internal'),
  ('supplier_raw_payload', 2, true, 'internal'),
  ('product_marketplace_attributes', 3, true, 'internal'),
  ('gtin_catalog', 4, true, 'internal'),
  ('mercado_livre_catalog', 5, true, 'external')
on conflict (provider) do nothing;

drop trigger if exists trg_gtin_catalog_updated_at
on public.gtin_catalog;

create trigger trg_gtin_catalog_updated_at
before update on public.gtin_catalog
for each row execute function public.set_updated_at();

drop trigger if exists trg_gtin_sources_updated_at
on public.gtin_sources;

create trigger trg_gtin_sources_updated_at
before update on public.gtin_sources
for each row execute function public.set_updated_at();

alter table public.gtin_catalog disable row level security;
alter table public.gtin_lookup_history disable row level security;
alter table public.gtin_sources disable row level security;

select
  'gtin_discovery_engine_ready' as status,
  (select count(*) from public.gtin_catalog) as catalog_records,
  (select count(*) from public.gtin_lookup_history) as lookup_records,
  (select count(*) from public.gtin_sources) as sources;
