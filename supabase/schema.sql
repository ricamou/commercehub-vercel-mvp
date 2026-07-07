create extension if not exists "uuid-ossp";

create table if not exists companies (
  id uuid primary key default uuid_generate_v4(),
  name text not null,
  document text,
  status text default 'active',
  created_at timestamptz default now()
);

create table if not exists users_app (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id),
  name text not null,
  email text unique not null,
  role text default 'owner',
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

create table if not exists listings (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id),
  product_id uuid references products(id),
  marketplace text not null,
  external_id text,
  status text default 'draft',
  payload jsonb default '{}',
  permalink text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
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

insert into companies (name, document, status)
values ('CommerceHub Demo', '00000000000000', 'active')
on conflict do nothing;