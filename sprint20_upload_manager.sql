-- ==========================================================
-- CommerceHub Sprint 20 - Upload Manager + Supabase Storage
-- Execute uma vez no Supabase > SQL Editor
-- ==========================================================

insert into storage.buckets (
  id,
  name,
  public,
  file_size_limit,
  allowed_mime_types
)
values (
  'product-images',
  'product-images',
  true,
  5242880,
  array['image/jpeg','image/png','image/webp']
)
on conflict (id)
do update set
  public = true,
  file_size_limit = 5242880,
  allowed_mime_types = array['image/jpeg','image/png','image/webp'];

alter table public.product_images
  add column if not exists storage_bucket text,
  add column if not exists storage_path text,
  add column if not exists file_name text,
  add column if not exists mime_type text,
  add column if not exists file_size bigint default 0,
  add column if not exists upload_status text default 'ready';

alter table public.listings
  add column if not exists auto_publish boolean not null default false,
  add column if not exists auto_publish_last_attempt timestamptz,
  add column if not exists auto_publish_attempts integer not null default 0;

create index if not exists idx_product_images_storage
  on public.product_images(company_id, storage_bucket, storage_path);

create index if not exists idx_listings_auto_publish
  on public.listings(company_id, marketplace, auto_publish, status);

insert into public.settings (company_id, key, value)
values (
  '00000000-0000-0000-0000-000000000001',
  'listing_automation',
  '{"enabled": false, "mode": "manual", "max_per_run": 10}'::jsonb
)
on conflict (company_id, key)
do nothing;

select
  'upload_manager_ready' as status,
  (select public from storage.buckets where id = 'product-images') as bucket_public,
  (select count(*) from public.product_images) as product_images,
  (select count(*) from public.listings where auto_publish = true) as automatic_listings;
