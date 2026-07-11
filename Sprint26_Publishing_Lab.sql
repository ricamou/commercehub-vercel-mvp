-- CommerceHub Sprint 26 - Publishing Lab
create table if not exists public.publishing_lab_runs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  marketplace text not null default 'mercado_livre',
  product_id uuid references public.products(id) on delete set null,
  listing_id uuid references public.listings(id) on delete set null,
  category_id text, status text not null default 'pending', score integer not null default 0,
  payload_preview jsonb not null default '{}', metadata_snapshot jsonb not null default '{}',
  conditional_snapshot jsonb not null default '{}', intelligence_snapshot jsonb not null default '{}',
  blockers jsonb not null default '[]', warnings jsonb not null default '[]', recommendations jsonb not null default '[]',
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create index if not exists idx_publishing_lab_runs_listing on public.publishing_lab_runs(listing_id,created_at desc);
alter table public.publishing_lab_runs disable row level security;
select 'publishing_lab_ready' as status,(select count(*) from public.publishing_lab_runs) as runs;
