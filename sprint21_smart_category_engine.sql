-- CommerceHub Sprint 21 - Smart Category Engine
create table if not exists public.ml_categories (
 id text primary key, site_id text not null default 'MLB', name text not null,
 path jsonb not null default '[]', settings jsonb not null default '{}', raw_data jsonb not null default '{}',
 last_synced_at timestamptz not null default now(), created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists public.ml_category_attributes (
 id uuid primary key default uuid_generate_v4(), category_id text not null references public.ml_categories(id) on delete cascade,
 attribute_id text not null, name text not null, value_type text, tags jsonb not null default '{}', values jsonb not null default '[]',
 required boolean not null default false, catalog_required boolean not null default false, raw_data jsonb not null default '{}',
 last_synced_at timestamptz not null default now(), created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(category_id, attribute_id)
);
create table if not exists public.product_marketplace_attributes (
 id uuid primary key default uuid_generate_v4(), company_id uuid not null references public.companies(id) on delete cascade,
 product_id uuid not null references public.products(id) on delete cascade, marketplace text not null default 'mercado_livre',
 category_id text, attribute_id text not null, value_id text, value_name text, source text not null default 'manual',
 confidence numeric(5,2), status text not null default 'active', raw_data jsonb not null default '{}',
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(), unique(product_id, marketplace, attribute_id)
);
create index if not exists idx_ml_category_attributes_category on public.ml_category_attributes(category_id, required desc, name);
create index if not exists idx_product_marketplace_attributes_product on public.product_marketplace_attributes(product_id, marketplace, category_id);
alter table public.ml_categories disable row level security;
alter table public.ml_category_attributes disable row level security;
alter table public.product_marketplace_attributes disable row level security;
select 'smart_category_engine_ready' as status,
 (select count(*) from public.ml_categories) categories,
 (select count(*) from public.ml_category_attributes) category_attributes,
 (select count(*) from public.product_marketplace_attributes) product_values;
