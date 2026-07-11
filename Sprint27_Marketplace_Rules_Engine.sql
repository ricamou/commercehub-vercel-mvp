-- ==========================================================
-- CommerceHub Sprint 27 - Marketplace Rules Engine
-- Execute em uma NOVA QUERY no Supabase SQL Editor
-- ==========================================================

create table if not exists public.marketplace_rule_snapshots (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  marketplace text not null default 'mercado_livre',
  category_id text not null,
  brand text,
  domain_id text,
  fingerprint text not null,
  decision_tree jsonb not null default '{}'::jsonb,
  official_metadata jsonb not null default '{}'::jsonb,
  conditional_metadata jsonb not null default '{}'::jsonb,
  payload_contract jsonb not null default '{}'::jsonb,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists uq_marketplace_rule_snapshot
on public.marketplace_rule_snapshots (
  marketplace,
  category_id,
  coalesce(brand, ''),
  coalesce(domain_id, ''),
  fingerprint
);

create table if not exists public.marketplace_rule_decisions (
  id uuid primary key default uuid_generate_v4(),
  snapshot_id uuid not null references public.marketplace_rule_snapshots(id) on delete cascade,
  rule_key text not null,
  input_state jsonb not null default '{}'::jsonb,
  outcome text not null,
  required_actions jsonb not null default '[]'::jsonb,
  explanation text,
  confidence numeric(5,2) not null default 100,
  created_at timestamptz not null default now()
);

create index if not exists idx_marketplace_rule_snapshots_lookup
on public.marketplace_rule_snapshots (
  marketplace,
  category_id,
  brand,
  active,
  updated_at desc
);

create index if not exists idx_marketplace_rule_decisions_snapshot
on public.marketplace_rule_decisions (
  snapshot_id,
  rule_key
);

drop trigger if exists trg_marketplace_rule_snapshots_updated_at
on public.marketplace_rule_snapshots;

create trigger trg_marketplace_rule_snapshots_updated_at
before update on public.marketplace_rule_snapshots
for each row execute function public.set_updated_at();

alter table public.marketplace_rule_snapshots disable row level security;
alter table public.marketplace_rule_decisions disable row level security;

select
  'marketplace_rules_engine_ready' as status,
  (select count(*) from public.marketplace_rule_snapshots) as snapshots,
  (select count(*) from public.marketplace_rule_decisions) as decisions;
