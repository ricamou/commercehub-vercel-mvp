-- ==========================================================
-- CommerceHub Sprint 19 - Listing Engine Mercado Livre
-- Execute uma vez no Supabase > SQL Editor
-- ==========================================================

alter table public.listings
  add column if not exists category_id text,
  add column if not exists listing_type_id text default 'gold_special',
  add column if not exists condition text default 'new',
  add column if not exists currency_id text default 'BRL',
  add column if not exists buying_mode text default 'buy_it_now',
  add column if not exists warranty text,
  add column if not exists validation_status text default 'pending',
  add column if not exists last_error text,
  add column if not exists last_synced_at timestamptz,
  add column if not exists item_url text;

create unique index if not exists uq_listings_product_marketplace
  on public.listings(company_id, product_id, marketplace);

create index if not exists idx_listings_marketplace_status
  on public.listings(company_id, marketplace, status);

create table if not exists public.listing_history (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid not null references public.companies(id) on delete cascade,
  listing_id uuid not null references public.listings(id) on delete cascade,
  product_id uuid references public.products(id) on delete set null,
  event_type text not null,
  old_status text,
  new_status text,
  message text,
  payload jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index if not exists idx_listing_history_listing
  on public.listing_history(listing_id, created_at desc);

alter table public.listing_history disable row level security;

select
  'listing_engine_ready' as status,
  (select count(*) from public.listings) as listings,
  (select count(*) from public.listing_history) as history;
