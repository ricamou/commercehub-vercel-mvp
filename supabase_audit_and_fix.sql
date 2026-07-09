create extension if not exists "uuid-ossp";
create extension if not exists pgcrypto;

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

create table if not exists users_app (
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
  document text,
  type text default 'manual',
  status text default 'active',
  config jsonb default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists products (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  supplier_id uuid references suppliers(id) on delete set null,
  sku text not null,
  name text not null,
  brand text,
  ean text,
  category text,
  description text,
  cost_price numeric default 0,
  sale_price numeric default 0,
  status text default 'active',
  raw_data jsonb default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique(company_id, sku)
);

create table if not exists inventory (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  product_id uuid references products(id) on delete cascade,
  sku text not null,
  quantity integer default 0,
  reserved integer default 0,
  status text default 'available',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists listings (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  product_id uuid references products(id) on delete cascade,
  marketplace text not null,
  external_id text,
  title text,
  price numeric default 0,
  status text default 'draft',
  payload jsonb default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
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
  product_id uuid references products(id) on delete set null,
  ai_type text not null,
  input jsonb default '{}',
  output jsonb default '{}',
  created_at timestamptz default now()
);

create table if not exists queue (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  job_type text not null,
  status text default 'pending',
  payload jsonb default '{}',
  attempts integer default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists webhooks (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  source text not null,
  event_type text,
  payload jsonb default '{}',
  processed boolean default false,
  created_at timestamptz default now()
);

create table if not exists sync_jobs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  sync_type text not null,
  status text default 'pending',
  started_at timestamptz,
  finished_at timestamptz,
  payload jsonb default '{}',
  created_at timestamptz default now()
);

alter table companies disable row level security;
alter table users_app disable row level security;
alter table suppliers disable row level security;
alter table products disable row level security;
alter table inventory disable row level security;
alter table listings disable row level security;
alter table orders disable row level security;
alter table oauth_tokens disable row level security;
alter table logs disable row level security;
alter table ai_history disable row level security;
alter table queue disable row level security;
alter table webhooks disable row level security;
alter table sync_jobs disable row level security;

insert into companies (id, name, document, plan, status)
values ('00000000-0000-0000-0000-000000000001', 'CommerceHub Demo', '00000000000000', 'enterprise', 'active')
on conflict (id) do update set name = excluded.name, updated_at = now();

insert into users_app (company_id, name, email, role, password_hash, status)
values ('00000000-0000-0000-0000-000000000001', 'Admin', 'admin@commercehub.local', 'admin', encode(digest('admin123', 'sha256'), 'hex'), 'active')
on conflict (email) do update set name = excluded.name, role = excluded.role, updated_at = now();

insert into logs (company_id, event_type, message, payload)
values ('00000000-0000-0000-0000-000000000001', 'supabase_audit', 'Audit SQL executado', '{"version":"sprint4"}');

select schemaname, tablename, rowsecurity
from pg_tables
where schemaname = 'public'
and tablename in ('companies','users_app','suppliers','products','inventory','listings','orders','oauth_tokens','logs','ai_history','queue','webhooks','sync_jobs')
order by tablename;