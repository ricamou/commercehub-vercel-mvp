-- ==========================================================
-- CommerceHub Sprint 32 - Marketplace Auto Completer
-- Execute em uma NOVA QUERY no Supabase SQL Editor
-- ==========================================================

create table if not exists public.ml_attribute_mapping_rules (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  marketplace text not null default 'mercado_livre',
  supplier text,
  category_id text,
  source_field text not null,
  target_attribute_id text not null,
  transform_type text not null default 'direct',
  transform_config jsonb not null default '{}'::jsonb,
  priority integer not null default 100,
  confidence numeric(5,2) not null default 100,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists uq_ml_attribute_mapping_rules
on public.ml_attribute_mapping_rules(
  marketplace,
  coalesce(supplier, ''),
  coalesce(category_id, ''),
  source_field,
  target_attribute_id
);

create table if not exists public.ml_auto_completion_runs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references public.companies(id) on delete cascade,
  product_id uuid not null references public.products(id) on delete cascade,
  listing_id uuid references public.listings(id) on delete cascade,
  category_id text not null,
  supplier text,
  status text not null default 'pending',
  completed_count integer not null default 0,
  missing_count integer not null default 0,
  completed_fields jsonb not null default '[]'::jsonb,
  missing_fields jsonb not null default '[]'::jsonb,
  detected_source_fields jsonb not null default '{}'::jsonb,
  applied_mappings jsonb not null default '[]'::jsonb,
  payload_preview jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_ml_auto_completion_runs_product
on public.ml_auto_completion_runs(product_id, created_at desc);

insert into public.ml_attribute_mapping_rules
(marketplace, supplier, category_id, source_field, target_attribute_id, transform_type, priority, confidence)
values
('mercado_livre','hayamax',null,'brand','BRAND','direct',10,100),
('mercado_livre','hayamax',null,'marca','BRAND','direct',10,100),
('mercado_livre','hayamax',null,'model','MODEL','direct',10,100),
('mercado_livre','hayamax',null,'modelo','MODEL','direct',10,100),
('mercado_livre','hayamax',null,'name','MODEL','fallback',50,80),
('mercado_livre','hayamax',null,'ean','GTIN','digits',10,100),
('mercado_livre','hayamax',null,'gtin','GTIN','digits',10,100),
('mercado_livre','hayamax',null,'barcode','GTIN','digits',10,100),
('mercado_livre','hayamax',null,'codigo_barras','GTIN','digits',10,100),
('mercado_livre','hayamax',null,'color','COLOR','direct',20,95),
('mercado_livre','hayamax',null,'cor','COLOR','direct',20,95),
('mercado_livre','hayamax',null,'main_color','MAIN_COLOR','direct',20,95),
('mercado_livre','hayamax',null,'with_lights','WITH_LIGHTS','boolean',20,90),
('mercado_livre','hayamax',null,'rgb','WITH_LIGHTS','boolean',30,85),
('mercado_livre','hayamax',null,'bluetooth','WITH_BLUETOOTH','boolean',20,90),
('mercado_livre','hayamax',null,'wireless','IS_WIRELESS','boolean',20,90),
('mercado_livre','hayamax',null,'with_wire','WITH_WIRE','boolean',20,90),
('mercado_livre','hayamax',null,'weight','WEIGHT','number',20,95),
('mercado_livre','hayamax',null,'height','HEIGHT','number',20,95),
('mercado_livre','hayamax',null,'width','WIDTH','number',20,95),
('mercado_livre','hayamax',null,'length','LENGTH','number',20,95),
('mercado_livre','hayamax',null,'mpn','MPN','direct',20,95),
('mercado_livre','hayamax',null,'manufacturer_part_number','MPN','direct',20,95)
on conflict do nothing;

drop trigger if exists trg_ml_attribute_mapping_rules_updated_at
on public.ml_attribute_mapping_rules;

create trigger trg_ml_attribute_mapping_rules_updated_at
before update on public.ml_attribute_mapping_rules
for each row execute function public.set_updated_at();

alter table public.ml_attribute_mapping_rules disable row level security;
alter table public.ml_auto_completion_runs disable row level security;

select
  'marketplace_auto_completer_ready' as status,
  (select count(*) from public.ml_attribute_mapping_rules) as mapping_rules,
  (select count(*) from public.ml_auto_completion_runs) as completion_runs;
