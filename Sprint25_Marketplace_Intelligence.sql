-- ==========================================================
-- CommerceHub Sprint 25 - Marketplace Intelligence Engine
-- Execute em uma NOVA QUERY no Supabase SQL Editor
-- ==========================================================

create table if not exists public.marketplace_rule_knowledge (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  marketplace text not null default 'mercado_livre',
  category_id text not null,
  domain_id text,
  brand text,
  rule_key text not null,
  rule_value jsonb not null default '{}',
  source text not null default 'api_feedback',
  confidence numeric(5,2) not null default 100,
  hit_count integer not null default 1,
  last_error_code text,
  last_error_message text,
  active boolean not null default true,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(marketplace, category_id, coalesce(domain_id,''), coalesce(brand,''), rule_key)
);

create table if not exists public.marketplace_error_knowledge (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  marketplace text not null default 'mercado_livre',
  product_id uuid references public.products(id) on delete set null,
  listing_id uuid references public.listings(id) on delete set null,
  category_id text,
  brand text,
  error_code text,
  cause_id text,
  department text,
  message text,
  payload_snapshot jsonb not null default '{}',
  response_snapshot jsonb not null default '{}',
  resolution_key text,
  resolved boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists idx_marketplace_rule_lookup
  on public.marketplace_rule_knowledge(
    marketplace,
    category_id,
    rule_key,
    active
  );

create index if not exists idx_marketplace_error_lookup
  on public.marketplace_error_knowledge(
    marketplace,
    category_id,
    error_code,
    created_at desc
  );

drop trigger if exists trg_marketplace_rule_knowledge_updated_at
  on public.marketplace_rule_knowledge;

create trigger trg_marketplace_rule_knowledge_updated_at
before update on public.marketplace_rule_knowledge
for each row execute function public.set_updated_at();

alter table public.marketplace_rule_knowledge disable row level security;
alter table public.marketplace_error_knowledge disable row level security;

select
  'marketplace_intelligence_ready' as status,
  (select count(*) from public.marketplace_rule_knowledge) as learned_rules,
  (select count(*) from public.marketplace_error_knowledge) as learned_errors;
