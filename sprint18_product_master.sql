-- ==========================================================
-- CommerceHub Sprint 18 - Product Master
-- Execute uma vez no Supabase > SQL Editor
-- ==========================================================

alter table public.products
  add column if not exists seo_name text,
  add column if not exists short_description text,
  add column if not exists ncm text,
  add column if not exists origin_code text,
  add column if not exists warranty_months integer default 0,
  add column if not exists internal_status text default 'draft',
  add column if not exists sync_status text default 'pending',
  add column if not exists last_synced_at timestamptz,
  add column if not exists primary_image_url text;

create table if not exists public.product_attributes (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid not null references public.companies(id) on delete cascade,
  product_id uuid not null references public.products(id) on delete cascade,
  name text not null,
  value text,
  unit text,
  is_required boolean not null default false,
  source text not null default 'commercehub',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(product_id, name)
);

create table if not exists public.product_suppliers (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid not null references public.companies(id) on delete cascade,
  product_id uuid not null references public.products(id) on delete cascade,
  supplier_id uuid not null references public.suppliers(id) on delete cascade,
  supplier_product_id uuid references public.supplier_products(id) on delete set null,
  supplier_sku text,
  external_id text,
  cost_price numeric(14,2) not null default 0,
  stock integer not null default 0,
  lead_time_days integer not null default 0,
  priority integer not null default 100,
  is_preferred boolean not null default false,
  status text not null default 'active',
  raw_data jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(product_id, supplier_id, external_id)
);

create table if not exists public.product_history (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid not null references public.companies(id) on delete cascade,
  product_id uuid not null references public.products(id) on delete cascade,
  event_type text not null,
  field_name text,
  old_value text,
  new_value text,
  source text not null default 'commercehub',
  message text,
  payload jsonb not null default '{}',
  created_at timestamptz not null default now()
);

alter table public.product_images
  add column if not exists alt_text text,
  add column if not exists source text default 'commercehub',
  add column if not exists hash text,
  add column if not exists updated_at timestamptz not null default now();

create index if not exists idx_products_search_sku on public.products(company_id, sku);
create index if not exists idx_products_search_ean on public.products(company_id, ean);
create index if not exists idx_products_search_name on public.products(company_id, name);
create index if not exists idx_product_attributes_product on public.product_attributes(product_id);
create index if not exists idx_product_suppliers_product on public.product_suppliers(product_id);
create index if not exists idx_product_history_product on public.product_history(product_id, created_at desc);
create index if not exists idx_product_images_product on public.product_images(product_id, position);

drop trigger if exists trg_product_attributes_updated_at on public.product_attributes;
create trigger trg_product_attributes_updated_at
before update on public.product_attributes
for each row execute function public.set_updated_at();

drop trigger if exists trg_product_suppliers_updated_at on public.product_suppliers;
create trigger trg_product_suppliers_updated_at
before update on public.product_suppliers
for each row execute function public.set_updated_at();

alter table public.product_attributes disable row level security;
alter table public.product_suppliers disable row level security;
alter table public.product_history disable row level security;

-- Vincula automaticamente as ofertas importadas da Sprint 17 ao catálogo mestre
insert into public.product_suppliers (
  company_id, product_id, supplier_id, supplier_product_id,
  supplier_sku, external_id, cost_price, stock, raw_data
)
select
  sp.company_id,
  sp.product_id,
  sp.supplier_id,
  sp.id,
  sp.sku,
  sp.external_id,
  sp.cost_price,
  sp.stock,
  sp.raw_data
from public.supplier_products sp
where sp.product_id is not null
on conflict (product_id, supplier_id, external_id)
do update set
  supplier_sku = excluded.supplier_sku,
  cost_price = excluded.cost_price,
  stock = excluded.stock,
  raw_data = excluded.raw_data,
  updated_at = now();

update public.products
set
  seo_name = coalesce(seo_name, name),
  short_description = coalesce(short_description, left(description, 240)),
  internal_status = coalesce(internal_status, 'draft'),
  sync_status = coalesce(sync_status, 'pending')
where company_id is not null;

select
  'product_master_ready' as status,
  (select count(*) from public.products) as products,
  (select count(*) from public.product_suppliers) as supplier_links,
  (select count(*) from public.product_attributes) as attributes,
  (select count(*) from public.product_history) as history;
