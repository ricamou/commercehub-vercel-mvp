-- ==========================================================
-- CommerceHub Enterprise V6
-- Sprint 45 - Order & Fulfillment Engine
-- Execute em NOVA QUERY no Supabase SQL Editor
-- ==========================================================

create table if not exists public.fulfillment_orders (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  marketplace_order_id uuid references public.marketplace_orders(id) on delete cascade,
  supplier_order_job_id uuid references public.supplier_order_jobs(id) on delete set null,
  marketplace text not null default 'mercado_livre',
  supplier_id uuid references public.suppliers(id) on delete set null,
  supplier_name text,
  external_order_id text not null,
  supplier_order_id text,
  status text not null default 'received',
  payment_status text,
  routing_status text not null default 'pending',
  fiscal_status text not null default 'pending',
  shipping_status text not null default 'pending',
  customer_notification_status text not null default 'pending',
  total_amount numeric(14,2),
  currency_id text,
  recipient_data jsonb not null default '{}'::jsonb,
  shipping_data jsonb not null default '{}'::jsonb,
  items_data jsonb not null default '[]'::jsonb,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create unique index if not exists uq_fulfillment_orders_marketplace_order
on public.fulfillment_orders(company_id, marketplace, external_order_id);

create index if not exists idx_fulfillment_orders_status
on public.fulfillment_orders(status, shipping_status, created_at desc);

create table if not exists public.fulfillment_invoices (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  fulfillment_order_id uuid not null references public.fulfillment_orders(id) on delete cascade,
  supplier_id uuid references public.suppliers(id) on delete set null,
  invoice_number text,
  invoice_series text,
  access_key text,
  issued_at timestamptz,
  issuer_document text,
  issuer_name text,
  recipient_document text,
  recipient_name text,
  total_amount numeric(14,2),
  xml_url text,
  danfe_url text,
  raw_payload jsonb not null default '{}'::jsonb,
  status text not null default 'received',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_fulfillment_invoices_order
on public.fulfillment_invoices(fulfillment_order_id, created_at desc);

create table if not exists public.fulfillment_trackings (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  fulfillment_order_id uuid not null references public.fulfillment_orders(id) on delete cascade,
  supplier_id uuid references public.suppliers(id) on delete set null,
  carrier text,
  tracking_code text,
  tracking_url text,
  shipped_at timestamptz,
  delivered_at timestamptz,
  status text not null default 'created',
  events jsonb not null default '[]'::jsonb,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_fulfillment_trackings_order
on public.fulfillment_trackings(fulfillment_order_id, created_at desc);

create table if not exists public.fulfillment_event_log (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  fulfillment_order_id uuid references public.fulfillment_orders(id) on delete cascade,
  event_type text not null,
  source text not null,
  status text,
  message text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_fulfillment_event_log_order
on public.fulfillment_event_log(fulfillment_order_id, created_at asc);

create table if not exists public.marketplace_customer_documents (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  fulfillment_order_id uuid not null references public.fulfillment_orders(id) on delete cascade,
  document_type text not null,
  title text not null,
  document_url text,
  document_key text,
  visible_to_customer boolean not null default true,
  marketplace_sync_status text not null default 'pending',
  marketplace_sync_response jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_marketplace_customer_documents_order
on public.marketplace_customer_documents(fulfillment_order_id, created_at desc);

drop trigger if exists trg_fulfillment_orders_updated_at
on public.fulfillment_orders;

create trigger trg_fulfillment_orders_updated_at
before update on public.fulfillment_orders
for each row execute function public.set_updated_at();

drop trigger if exists trg_fulfillment_invoices_updated_at
on public.fulfillment_invoices;

create trigger trg_fulfillment_invoices_updated_at
before update on public.fulfillment_invoices
for each row execute function public.set_updated_at();

drop trigger if exists trg_fulfillment_trackings_updated_at
on public.fulfillment_trackings;

create trigger trg_fulfillment_trackings_updated_at
before update on public.fulfillment_trackings
for each row execute function public.set_updated_at();

drop trigger if exists trg_marketplace_customer_documents_updated_at
on public.marketplace_customer_documents;

create trigger trg_marketplace_customer_documents_updated_at
before update on public.marketplace_customer_documents
for each row execute function public.set_updated_at();

alter table public.fulfillment_orders disable row level security;
alter table public.fulfillment_invoices disable row level security;
alter table public.fulfillment_trackings disable row level security;
alter table public.fulfillment_event_log disable row level security;
alter table public.marketplace_customer_documents disable row level security;

select
  'order_fulfillment_engine_ready' as status,
  (select count(*) from public.fulfillment_orders) as fulfillment_orders,
  (select count(*) from public.fulfillment_invoices) as invoices,
  (select count(*) from public.fulfillment_trackings) as trackings;
