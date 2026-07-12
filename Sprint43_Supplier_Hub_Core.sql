create table if not exists public.supplier_hub_connectors (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  supplier_id uuid references public.suppliers(id) on delete cascade,
  supplier_name text not null,
  adapter_key text not null,
  connector_type text not null default 'api',
  status text not null default 'draft',
  base_url text,
  auth_type text not null default 'none',
  capabilities jsonb not null default '{}'::jsonb,
  settings jsonb not null default '{}'::jsonb,
  last_health_check_at timestamptz,
  last_sync_at timestamptz,
  last_error text,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists uq_supplier_hub_connectors
on public.supplier_hub_connectors(company_id, adapter_key);

create table if not exists public.supplier_product_mappings (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  supplier_id uuid references public.suppliers(id) on delete cascade,
  product_id uuid references public.products(id) on delete cascade,
  supplier_sku text not null,
  supplier_product_id text,
  supplier_variant_id text,
  supplier_barcode text,
  supplier_data jsonb not null default '{}'::jsonb,
  priority integer not null default 1,
  is_primary boolean not null default true,
  active boolean not null default true,
  last_price numeric(14,4),
  last_stock integer,
  last_sync_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists uq_supplier_product_mapping
on public.supplier_product_mappings(company_id, supplier_id, supplier_sku);

create table if not exists public.supplier_pricing_rules (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  supplier_id uuid references public.suppliers(id) on delete cascade,
  marketplace text not null default 'mercado_livre',
  markup_type text not null default 'percentage',
  markup_value numeric(10,4) not null default 8,
  include_shipping_cost boolean not null default false,
  minimum_margin numeric(10,4),
  rounding_mode text not null default 'none',
  rounding_value numeric(10,2),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists uq_supplier_pricing_rule
on public.supplier_pricing_rules(company_id, supplier_id, marketplace);

create table if not exists public.supplier_sync_runs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  supplier_id uuid references public.suppliers(id) on delete cascade,
  adapter_key text not null,
  sync_type text not null default 'catalog',
  status text not null default 'running',
  products_seen integer not null default 0,
  products_created integer not null default 0,
  products_updated integer not null default 0,
  prices_updated integer not null default 0,
  stocks_updated integer not null default 0,
  errors_count integer not null default 0,
  summary jsonb not null default '{}'::jsonb,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.supplier_hub_logs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  supplier_id uuid references public.suppliers(id) on delete cascade,
  connector_id uuid references public.supplier_hub_connectors(id) on delete set null,
  level text not null default 'info',
  event_type text not null,
  message text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

drop trigger if exists trg_supplier_hub_connectors_updated_at on public.supplier_hub_connectors;
create trigger trg_supplier_hub_connectors_updated_at
before update on public.supplier_hub_connectors
for each row execute function public.set_updated_at();

drop trigger if exists trg_supplier_product_mappings_updated_at on public.supplier_product_mappings;
create trigger trg_supplier_product_mappings_updated_at
before update on public.supplier_product_mappings
for each row execute function public.set_updated_at();

drop trigger if exists trg_supplier_pricing_rules_updated_at on public.supplier_pricing_rules;
create trigger trg_supplier_pricing_rules_updated_at
before update on public.supplier_pricing_rules
for each row execute function public.set_updated_at();

alter table public.supplier_hub_connectors disable row level security;
alter table public.supplier_product_mappings disable row level security;
alter table public.supplier_pricing_rules disable row level security;
alter table public.supplier_sync_runs disable row level security;
alter table public.supplier_hub_logs disable row level security;

select
  'supplier_hub_core_ready' as status,
  (select count(*) from public.supplier_hub_connectors) as connectors,
  (select count(*) from public.supplier_product_mappings) as mappings,
  (select count(*) from public.supplier_pricing_rules) as pricing_rules;
