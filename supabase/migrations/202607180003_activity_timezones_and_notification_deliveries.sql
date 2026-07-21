alter table public.activities add column if not exists timezone text;

update public.activities activity
set timezone = profile.timezone
from public.profiles profile
where activity.user_id = profile.id and activity.timezone is null;

alter table public.activities alter column timezone set default 'UTC';
alter table public.activities alter column timezone set not null;

create table if not exists public.notification_deliveries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  kind text not null check (kind in ('diary', 'activity', 'weekly_recap')),
  local_date date not null,
  created_at timestamptz not null default now(),
  unique (user_id, kind, local_date)
);

alter table public.notification_deliveries enable row level security;
create index if not exists notification_deliveries_user_date_idx on public.notification_deliveries(user_id, local_date desc);
