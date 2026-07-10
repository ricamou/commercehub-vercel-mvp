-- ==========================================================
-- CommerceHub Sprint 20.1 - Image Manager Enterprise
-- Execute em uma NOVA QUERY no Supabase SQL Editor
-- ==========================================================

alter table public.product_images
  add column if not exists deleted_at timestamptz,
  add column if not exists validation_status text default 'pending',
  add column if not exists validation_message text;

create index if not exists idx_product_images_active_order
  on public.product_images(product_id, position)
  where deleted_at is null;

update public.product_images
set
  validation_status = case
    when url like 'https://%' or url like 'http://%' then 'pending'
    else 'invalid'
  end,
  validation_message = case
    when url like 'https://%' or url like 'http://%' then null
    else 'Caminho local ou URL inválida'
  end
where validation_status is null
   or validation_status = 'pending';

select
  'image_manager_ready' as status,
  count(*) filter (where deleted_at is null) as active_images,
  count(*) filter (where validation_status = 'invalid') as invalid_images
from public.product_images;
