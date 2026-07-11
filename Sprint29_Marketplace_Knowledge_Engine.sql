-- ==========================================================
-- CommerceHub Sprint 29 - Marketplace Knowledge Engine
-- Execute em uma NOVA QUERY no Supabase SQL Editor
-- ==========================================================

create table if not exists public.ml_knowledge_profiles (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  category_id text not null,
  brand text,
  domain_id text,
  fingerprint text not null,
  status text not null default 'active',
  confidence numeric(5,2) not null default 100,
  evidence_count integer not null default 1,
  profile jsonb not null default '{}'::jsonb,
  official_sources jsonb not null default '[]'::jsonb,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists uq_ml_knowledge_profiles
on public.ml_knowledge_profiles (
  category_id,
  coalesce(brand, ''),
  coalesce(domain_id, ''),
  fingerprint
);

create table if not exists public.ml_knowledge_rules (
  id uuid primary key default uuid_generate_v4(),
  profile_id uuid not null references public.ml_knowledge_profiles(id) on delete cascade,
  rule_key text not null,
  field_name text,
  rule_scope text not null default 'category',
  required boolean not null default false,
  conditional boolean not null default false,
  location text,
  accepted_format text,
  accepted_values jsonb not null default '[]'::jsonb,
  outcome text not null default 'informational',
  explanation text,
  source_endpoint text,
  evidence jsonb not null default '{}'::jsonb,
  confidence numeric(5,2) not null default 100,
  created_at timestamptz not null default now()
);

create index if not exists idx_ml_knowledge_profiles_lookup
on public.ml_knowledge_profiles (
  category_id,
  brand,
  status,
  updated_at desc
);

create index if not exists idx_ml_knowledge_rules_profile
on public.ml_knowledge_rules (
  profile_id,
  rule_key,
  field_name
);

drop trigger if exists trg_ml_knowledge_profiles_updated_at
on public.ml_knowledge_profiles;

create trigger trg_ml_knowledge_profiles_updated_at
before update on public.ml_knowledge_profiles
for each row execute function public.set_updated_at();

alter table public.ml_knowledge_profiles disable row level security;
alter table public.ml_knowledge_rules disable row level security;

select
  'marketplace_knowledge_engine_ready' as status,
  (select count(*) from public.ml_knowledge_profiles) as profiles,
  (select count(*) from public.ml_knowledge_rules) as rules;
