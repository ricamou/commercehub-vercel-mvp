create table if not exists public.marketplace_orders (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  marketplace text not null default 'mercado_livre',
  external_order_id text not null,
  buyer_id text,
  status text,
  payment_status text,
  shipment_id text,
  total_amount numeric(14,2),
  currency_id text,
  order_data jsonb not null default '{}'::jsonb,
  buyer_data jsonb not null default '{}'::jsonb,
  shipping_data jsonb not null default '{}'::jsonb,
  date_created timestamptz,
  last_updated timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists uq_marketplace_orders
on public.marketplace_orders(marketplace, external_order_id);

create table if not exists public.marketplace_order_items (
  id uuid primary key default uuid_generate_v4(),
  order_id uuid not null references public.marketplace_orders(id) on delete cascade,
  listing_id uuid references public.listings(id) on delete set null,
  product_id uuid references public.products(id) on delete set null,
  external_item_id text,
  supplier text,
  supplier_sku text,
  title text,
  quantity integer not null default 1,
  unit_price numeric(14,2),
  item_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_marketplace_order_items_order
on public.marketplace_order_items(order_id);

create table if not exists public.supplier_order_jobs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  marketplace_order_id uuid not null references public.marketplace_orders(id) on delete cascade,
  supplier text not null,
  status text not null default 'pending',
  dispatch_mode text not null default 'manual',
  supplier_order_id text,
  request_payload jsonb not null default '{}'::jsonb,
  response_payload jsonb not null default '{}'::jsonb,
  invoice_number text,
  invoice_key text,
  invoice_url text,
  tracking_code text,
  tracking_url text,
  carrier text,
  error_message text,
  sent_at timestamptz,
  confirmed_at timestamptz,
  shipped_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_supplier_order_jobs_status
on public.supplier_order_jobs(status, supplier, created_at);

create table if not exists public.supplier_connector_capabilities (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  supplier text not null,
  create_order_enabled boolean not null default false,
  order_status_enabled boolean not null default false,
  invoice_enabled boolean not null default false,
  tracking_enabled boolean not null default false,
  dispatch_mode text not null default 'manual',
  endpoint_config jsonb not null default '{}'::jsonb,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists uq_supplier_connector_capabilities
on public.supplier_connector_capabilities(company_id, supplier);

create table if not exists public.order_event_log (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  marketplace_order_id uuid references public.marketplace_orders(id) on delete cascade,
  supplier_order_job_id uuid references public.supplier_order_jobs(id) on delete cascade,
  event_type text not null,
  source text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_order_event_log_order
on public.order_event_log(marketplace_order_id, created_at);

insert into public.supplier_connector_capabilities (
  company_id, supplier, dispatch_mode, create_order_enabled,
  order_status_enabled, invoice_enabled, tracking_enabled
)
values (
  '00000000-0000-0000-0000-000000000001',
  'hayamax',
  'manual',
  false,
  false,
  false,
  false
)
on conflict (company_id, supplier) do nothing;

drop trigger if exists trg_marketplace_orders_updated_at on public.marketplace_orders;
create trigger trg_marketplace_orders_updated_at
before update on public.marketplace_orders
for each row execute function public.set_updated_at();

drop trigger if exists trg_supplier_order_jobs_updated_at on public.supplier_order_jobs;
create trigger trg_supplier_order_jobs_updated_at
before update on public.supplier_order_jobs
for each row execute function public.set_updated_at();

drop trigger if exists trg_supplier_connector_capabilities_updated_at on public.supplier_connector_capabilities;
create trigger trg_supplier_connector_capabilities_updated_at
before update on public.supplier_connector_capabilities
for each row execute function public.set_updated_at();

alter table public.marketplace_orders disable row level security;
alter table public.marketplace_order_items disable row level security;
alter table public.supplier_order_jobs disable row level security;
alter table public.supplier_connector_capabilities disable row level security;
alter table public.order_event_log disable row level security;

select
  'order_orchestrator_ready' as status,
  (select count(*) from public.marketplace_orders) as orders,
  (select count(*) from public.supplier_order_jobs) as supplier_jobs,
  (select count(*) from public.supplier_connector_capabilities) as connectors;
