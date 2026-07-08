create extension if not exists "uuid-ossp";

create table if not exists companies (
  id uuid primary key default uuid_generate_v4(),
  name text not null,
  document text,
  plan text default 'starter',
  status text default 'active',
  created_at timestamptz default now()
);

create table if not exists users_app (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id),
  name text not null,
  email text not null unique,
  role text default 'admin',
  password_hash text,
  status text default 'active',
  created_at timestamptz default now()
);

create table if not exists suppliers (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id),
  name text not null,
  type text default 'manual',
  status text default 'active',
  config jsonb default '{}',
  created_at timestamptz default now()
);

create table if not exists products (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id),
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
  updated_at timestamptz default now()
);



create table if not exists inventory_movements (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id),
  product_id uuid,
  sku text,
  movement_type text default 'set',
  quantity integer default 0,
  previous_stock integer default 0,
  new_stock integer default 0,
  source text default 'manual',
  created_at timestamptz default now()
);

create table if not exists listings (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id),
  product_id uuid references products(id),
  marketplace text not null,
  external_id text,
  status text default 'draft',
  payload jsonb default '{}',
  permalink text,
  created_at timestamptz default now()
);

create table if not exists orders (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id),
  marketplace text not null,
  external_order_id text,
  status text,
  total_amount numeric default 0,
  payload jsonb default '{}',
  created_at timestamptz default now()
);

create table if not exists events (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id),
  event_type text not null,
  message text,
  payload jsonb default '{}',
  created_at timestamptz default now()
);

create table if not exists oauth_tokens (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id),
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