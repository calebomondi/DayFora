alter table public.activities
  add column if not exists reminder_time time,
  add column if not exists current_streak integer not null default 0 check (current_streak >= 0),
  add column if not exists longest_streak integer not null default 0 check (longest_streak >= 0),
  add column if not exists completed_at timestamptz;

alter table public.activity_checkins
  add column if not exists next_small_step text;

create type public.activity_event_type as enum ('checkin', 'streak_reset', 'paused', 'resumed', 'completed');

create table public.activity_events (
  id uuid primary key default gen_random_uuid(),
  activity_id uuid not null references public.activities(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  local_date date not null,
  event_type public.activity_event_type not null,
  checkin_id uuid references public.activity_checkins(id) on delete set null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (activity_id, local_date, event_type)
);

create table public.activity_recaps (
  id uuid primary key default gen_random_uuid(),
  activity_id uuid not null unique references public.activities(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  payload jsonb not null,
  status public.recap_status not null default 'ready_for_review',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index activity_events_activity_date_idx on public.activity_events(activity_id, local_date desc);
create index activity_events_user_date_idx on public.activity_events(user_id, local_date desc);
create index activity_recaps_user_activity_idx on public.activity_recaps(user_id, activity_id);

create trigger activity_recaps_set_updated_at before update on public.activity_recaps
for each row execute function public.set_updated_at();

grant select, insert, update, delete on public.activity_events, public.activity_recaps to authenticated;

alter table public.activity_events enable row level security;
alter table public.activity_recaps enable row level security;

create policy "activity events are private" on public.activity_events for all to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

create policy "activity recaps are private" on public.activity_recaps for all to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
