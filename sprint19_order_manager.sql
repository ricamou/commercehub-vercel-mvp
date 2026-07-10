-- ==========================================================
-- CommerceHub Sprint 19 - Order Manager
-- Execute uma vez no Supabase > SQL Editor
-- ==========================================================

alter table public.orders
  add column if not exists payment_status text default 'pending',
  add column if not exists shipping_status text default 'pending',
  add column if not exists shipping_id text,
  add column if not exists currency_id text default 'BRL',
  add column if not exists buyer_id text,
  add column if not exists buyer_nickname text,
  add column if not exists date_closed timestamptz,
  add column if not exists last_synced_at timestamptz;

create unique index if not exists uq_orders_marketplace_external
  on public.orders(company_id, marketplace, external_order_id);

alter table public.order_items
  add column if not exists external_item_id text,
  add column if not exists variation_id text,
  add column if not exists seller_sku text;

create table if not exists public.order_status_history (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid not null references public.companies(id) on delete cascade,
  order_id uuid not null references public.orders(id) on delete cascade,
  old_status text,
  new_status text not null,
  source text not null default 'commercehub',
  message text,
  payload jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index if not exists idx_order_status_history_order
  on public.order_status_history(order_id, created_at desc);

create index if not exists idx_orders_company_created
  on public.orders(company_id, created_at desc);

create index if not exists idx_orders_status
  on public.orders(company_id, status);

create index if not exists idx_order_items_order
  on public.order_items(order_id);

alter table public.order_status_history disable row level security;

select
  'order_manager_ready' as status,
  (select count(*) from public.orders) as orders,
  (select count(*) from public.order_items) as order_items,
  (select count(*) from public.order_status_history) as history;
