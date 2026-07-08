create extension if not exists "uuid-ossp";

create table if not exists companies (
  id uuid primary key default uuid_generate_v4(),
  name text not null,
  document text,
  plan text default 'starter',
  status text default 'active',
  settings jsonb default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists users (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  name text not null,
  email text not null unique,
  role text default 'admin',
  password_hash text,
  status text default 'active',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists suppliers (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  name text not null,
  type text default 'manual',
  status text default 'active',
  config jsonb default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists products (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  supplier_id uuid references suppliers(id),
  sku text not null,
  name text not null,
  brand text,
  ean text,
  category text,
  description text,
  cost_price numeric default 0,
  sale_price numeric default 0,
  stock integer default 0,
  status text default 'active',
  raw_data jsonb default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique(company_id, sku)
);

create table if not exists inventory (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  product_id uuid references products(id),
  sku text,
  movement_type text default 'set',
  quantity integer default 0,
  previous_stock integer default 0,
  new_stock integer default 0,
  source text default 'manual',
  created_at timestamptz default now()
);

create table if not exists orders (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  marketplace text not null,
  external_order_id text,
  status text,
  total_amount numeric default 0,
  payload jsonb default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists listings (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  product_id uuid references products(id),
  marketplace text not null,
  external_id text,
  status text default 'draft',
  payload jsonb default '{}',
  permalink text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists oauth_tokens (
  id text primary key,
  company_id uuid references companies(id) on delete cascade,
  marketplace text not null,
  access_token text,
  refresh_token text,
  user_id text,
  expires_in integer,
  token_type text default 'Bearer',
  scope text,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique(company_id, marketplace)
);

create table if not exists logs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  event_type text not null,
  message text,
  payload jsonb default '{}',
  created_at timestamptz default now()
);

create table if not exists ai_history (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  action text not null,
  input jsonb default '{}',
  output jsonb default '{}',
  created_at timestamptz default now()
);

create table if not exists queue (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  job_type text not null,
  status text default 'queued',
  payload jsonb default '{}',
  result jsonb default '{}',
  attempts integer default 0,
  created_at timestamptz default now(),
  processed_at timestamptz
);

create table if not exists webhooks (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  marketplace text not null,
  event_type text,
  payload jsonb default '{}',
  status text default 'received',
  created_at timestamptz default now()
);

create table if not exists sync_jobs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  sync_type text not null,
  status text default 'queued',
  payload jsonb default '{}',
  result jsonb default '{}',
  created_at timestamptz default now(),
  finished_at timestamptz
);

create index if not exists idx_products_company_sku on products(company_id, sku);
create index if not exists idx_orders_company_marketplace on orders(company_id, marketplace);
create index if not exists idx_logs_company_created on logs(company_id, created_at desc);
create index if not exists idx_queue_status on queue(status);
create index if not exists idx_sync_jobs_status on sync_jobs(status);