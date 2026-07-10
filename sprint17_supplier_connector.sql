-- ==========================================================
-- CommerceHub Sprint 17 - Universal Supplier Connector
-- Execute uma vez no Supabase > SQL Editor
-- ==========================================================

create table if not exists public.supplier_products (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid not null references public.companies(id) on delete cascade,
  supplier_id uuid not null references public.suppliers(id) on delete cascade,
  external_id text not null,
  sku text,
  ean text,
  name text not null,
  brand text,
  category text,
  description text,
  cost_price numeric(14,2) not null default 0,
  sale_price numeric(14,2) not null default 0,
  stock integer not null default 0,
  image_url text,
  status text not null default 'active',
  source_format text,
  source_updated_at timestamptz,
  raw_data jsonb not null default '{}',
  product_id uuid references public.products(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(company_id, supplier_id, external_id)
);

create index if not exists idx_supplier_products_supplier
  on public.supplier_products(company_id, supplier_id);

create index if not exists idx_supplier_products_sku
  on public.supplier_products(company_id, sku);

create index if not exists idx_supplier_products_ean
  on public.supplier_products(company_id, ean);

drop trigger if exists trg_supplier_products_updated_at on public.supplier_products;
create trigger trg_supplier_products_updated_at
before update on public.supplier_products
for each row execute function public.set_updated_at();

alter table public.supplier_products disable row level security;

select
  'supplier_connector_ready' as status,
  count(*) as supplier_products
from public.supplier_products;
