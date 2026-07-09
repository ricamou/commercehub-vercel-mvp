create extension if not exists "uuid-ossp";
create extension if not exists pgcrypto;

create table if not exists public.companies (
  id uuid primary key default uuid_generate_v4(),
  name text not null,
  legal_name text,
  document text,
  email text,
  phone text,
  plan text not null default 'starter',
  status text not null default 'active',
  settings jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.users_app (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  name text not null,
  email text not null unique,
  role text not null default 'admin',
  password_hash text,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.settings (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  key text not null,
  value jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(company_id, key)
);

create table if not exists public.suppliers (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  name text not null,
  document text,
  email text,
  phone text,
  type text not null default 'manual',
  status text not null default 'active',
  config jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.categories (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  parent_id uuid references public.categories(id) on delete set null,
  name text not null,
  marketplace text,
  external_id text,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.brands (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  name text not null,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(company_id, name)
);

create table if not exists public.products (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  supplier_id uuid references public.suppliers(id) on delete set null,
  category_id uuid references public.categories(id) on delete set null,
  brand_id uuid references public.brands(id) on delete set null,
  sku text not null,
  name text not null,
  brand text,
  ean text,
  description text,
  cost_price numeric(14,2) not null default 0,
  sale_price numeric(14,2) not null default 0,
  weight_kg numeric(14,3),
  height_cm numeric(14,2),
  width_cm numeric(14,2),
  length_cm numeric(14,2),
  status text not null default 'active',
  raw_data jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(company_id, sku)
);

create table if not exists public.product_images (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  product_id uuid references public.products(id) on delete cascade,
  url text not null,
  position integer not null default 0,
  is_main boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists public.inventory (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  product_id uuid references public.products(id) on delete cascade,
  sku text not null,
  quantity integer not null default 0,
  reserved integer not null default 0,
  available integer generated always as (quantity - reserved) stored,
  status text not null default 'available',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(company_id, product_id)
);

create table if not exists public.inventory_movements (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  product_id uuid references public.products(id) on delete set null,
  sku text not null,
  movement_type text not null,
  quantity integer not null,
  reference_type text,
  reference_id text,
  notes text,
  payload jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists public.marketplace_accounts (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  marketplace text not null,
  account_name text,
  external_user_id text,
  status text not null default 'disconnected',
  config jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(company_id, marketplace)
);

create table if not exists public.oauth_tokens (
  id text primary key,
  company_id uuid references public.companies(id) on delete cascade,
  marketplace text not null,
  access_token text,
  refresh_token text,
  user_id text,
  expires_in integer,
  expires_at timestamptz,
  token_type text not null default 'Bearer',
  scope text,
  raw_data jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(company_id, marketplace)
);

create table if not exists public.listings (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  product_id uuid references public.products(id) on delete cascade,
  marketplace text not null,
  external_id text,
  title text not null,
  description text,
  price numeric(14,2) not null default 0,
  available_quantity integer not null default 0,
  status text not null default 'draft',
  permalink text,
  payload jsonb not null default '{}',
  published_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.orders (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  marketplace text not null,
  external_order_id text,
  buyer_name text,
  buyer_email text,
  status text not null default 'created',
  total_amount numeric(14,2) not null default 0,
  shipping_amount numeric(14,2) not null default 0,
  paid_at timestamptz,
  raw_data jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.order_items (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  order_id uuid references public.orders(id) on delete cascade,
  product_id uuid references public.products(id) on delete set null,
  sku text,
  title text,
  quantity integer not null default 1,
  unit_price numeric(14,2) not null default 0,
  total_price numeric(14,2) not null default 0,
  raw_data jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists public.queue (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  job_type text not null,
  status text not null default 'pending',
  priority integer not null default 0,
  attempts integer not null default 0,
  payload jsonb not null default '{}',
  last_error text,
  scheduled_at timestamptz,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.sync_jobs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  sync_type text not null,
  marketplace text,
  status text not null default 'pending',
  payload jsonb not null default '{}',
  result jsonb not null default '{}',
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.sync_logs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  sync_job_id uuid references public.sync_jobs(id) on delete cascade,
  level text not null default 'info',
  message text,
  payload jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists public.webhooks (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  source text not null,
  event_type text,
  external_id text,
  processed boolean not null default false,
  payload jsonb not null default '{}',
  received_at timestamptz not null default now(),
  processed_at timestamptz
);

create table if not exists public.ai_history (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  product_id uuid references public.products(id) on delete set null,
  ai_type text not null,
  input jsonb not null default '{}',
  output jsonb not null default '{}',
  model text,
  created_at timestamptz not null default now()
);

create table if not exists public.logs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  event_type text not null,
  level text not null default 'info',
  message text,
  payload jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists public.audit_logs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  actor_user_id uuid references public.users_app(id) on delete set null,
  action text not null,
  entity_type text,
  entity_id text,
  before_data jsonb,
  after_data jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.notifications (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  user_id uuid references public.users_app(id) on delete cascade,
  title text not null,
  message text,
  type text not null default 'info',
  read_at timestamptz,
  payload jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

do $$
declare
  t text;
begin
  foreach t in array array['companies','users_app','settings','suppliers','categories','brands','products','inventory','marketplace_accounts','oauth_tokens','listings','orders','queue']
  loop
    execute format('drop trigger if exists trg_%s_updated_at on public.%I', t, t);
    execute format('create trigger trg_%s_updated_at before update on public.%I for each row execute function public.set_updated_at()', t, t);
  end loop;
end $$;

create index if not exists idx_products_company_id on public.products(company_id);
create index if not exists idx_products_sku on public.products(sku);
create index if not exists idx_inventory_sku on public.inventory(sku);
create index if not exists idx_logs_company_created_at on public.logs(company_id, created_at desc);
create index if not exists idx_queue_status_scheduled on public.queue(status, scheduled_at);
create index if not exists idx_webhooks_processed on public.webhooks(processed, received_at);

insert into public.companies (id, name, legal_name, document, email, plan, status, settings)
values ('00000000-0000-0000-0000-000000000001','CommerceHub Demo','CommerceHub Demo LTDA','00000000000000','admin@commercehub.local','enterprise','active','{"currency":"BRL","timezone":"America/Sao_Paulo"}')
on conflict (id) do update set name = excluded.name, updated_at = now();

insert into public.users_app (company_id, name, email, role, password_hash, status)
values ('00000000-0000-0000-0000-000000000001','Admin','admin@commercehub.local','admin',encode(digest('admin123','sha256'),'hex'),'active')
on conflict (email) do update set name = excluded.name, updated_at = now();

insert into public.suppliers (id, company_id, name, type, status)
values ('00000000-0000-0000-0000-000000000101','00000000-0000-0000-0000-000000000001','Fornecedor Manual','manual','active')
on conflict (id) do update set name = excluded.name, updated_at = now();

insert into public.brands (id, company_id, name, status)
values ('00000000-0000-0000-0000-000000000201','00000000-0000-0000-0000-000000000001','CommerceHub','active')
on conflict (id) do update set name = excluded.name, updated_at = now();

insert into public.categories (id, company_id, name, marketplace, status)
values ('00000000-0000-0000-0000-000000000301','00000000-0000-0000-0000-000000000001','Acessórios','mercadolivre','active')
on conflict (id) do update set name = excluded.name, updated_at = now();

insert into public.products (id, company_id, supplier_id, category_id, brand_id, sku, name, brand, ean, description, cost_price, sale_price, status, raw_data)
values ('00000000-0000-0000-0000-000000000401','00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000101','00000000-0000-0000-0000-000000000301','00000000-0000-0000-0000-000000000201','CH-TEST-001','Produto Teste CommerceHub','CommerceHub','7890000000000','Produto criado para teste real.',25.00,59.90,'active','{"source":"seed"}')
on conflict (company_id, sku) do update set name = excluded.name, updated_at = now();

insert into public.inventory (company_id, product_id, sku, quantity, reserved, status)
values ('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000401','CH-TEST-001',10,0,'available')
on conflict (company_id, product_id) do update set quantity = excluded.quantity, updated_at = now();

insert into public.marketplace_accounts (company_id, marketplace, account_name, status)
values ('00000000-0000-0000-0000-000000000001','mercadolivre','Mercado Livre Demo','disconnected')
on conflict (company_id, marketplace) do update set account_name = excluded.account_name, updated_at = now();

insert into public.logs (company_id, event_type, level, message, payload)
values ('00000000-0000-0000-0000-000000000001','database_foundation','info','CommerceHub Sprint 9 schema executado com sucesso','{"version":"enterprise-v5-sprint9-database-foundation"}');

select 'commercehub_schema_ready' as status,
(select count(*) from public.companies) as companies,
(select count(*) from public.products) as products,
(select count(*) from public.inventory) as inventory,
(select count(*) from public.logs) as logs;