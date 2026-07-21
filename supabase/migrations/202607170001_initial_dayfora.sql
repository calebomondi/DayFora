create extension if not exists pgcrypto;

create type public.diary_entry_status as enum ('draft', 'processing', 'ready_for_review', 'approved', 'discarded', 'processing_failed');
create type public.capture_origin as enum ('diary', 'activity');
create type public.capture_status as enum ('pending_upload', 'uploaded', 'processing', 'processed', 'failed', 'deleted');
create type public.media_type as enum ('audio', 'image');
create type public.media_processing_status as enum ('pending', 'processing', 'complete', 'failed');
create type public.upload_source as enum ('in_app', 'user_selected');
create type public.cadence_type as enum ('daily', 'weekdays', 'weekly', 'custom');
create type public.activity_status as enum ('active', 'paused', 'completed', 'archived');
create type public.checkin_status as enum ('approved', 'discarded');
create type public.draft_status as enum ('ready_for_review', 'approved', 'discarded', 'superseded', 'failed');
create type public.provenance_source as enum ('user_written', 'transcribed', 'ai_generated');
create type public.device_platform as enum ('android', 'ios');
create type public.recap_status as enum ('ready_for_review', 'approved', 'discarded', 'failed');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null default '',
  timezone text not null default 'UTC',
  diary_reminder_time time,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.diary_entries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  local_date date not null,
  title text not null default '',
  body text not null default '',
  mood text,
  status public.diary_entry_status not null default 'draft',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, local_date)
);

create table public.activities (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  title text not null check (char_length(trim(title)) > 0),
  purpose text,
  start_date date not null,
  end_date date,
  cadence_type public.cadence_type not null,
  cadence_config jsonb not null default '{}'::jsonb,
  timezone text not null default 'UTC',
  status public.activity_status not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (end_date is null or end_date >= start_date)
);

create table public.captures (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  initiated_from public.capture_origin not null,
  requested_activity_id uuid references public.activities(id) on delete set null,
  local_date date not null,
  raw_text text,
  status public.capture_status not null default 'pending_upload',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.media_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  storage_path text not null unique check (storage_path like 'users/' || user_id::text || '/%'),
  media_type public.media_type not null,
  captured_at timestamptz,
  upload_source public.upload_source not null,
  processing_status public.media_processing_status not null default 'pending',
  transcript text,
  ai_description jsonb,
  created_at timestamptz not null default now()
);

create table public.entry_media (
  entry_id uuid not null references public.diary_entries(id) on delete cascade,
  media_item_id uuid not null references public.media_items(id) on delete cascade,
  role text not null check (role in ('source', 'attachment')),
  primary key (entry_id, media_item_id)
);

create table public.capture_media (
  capture_id uuid not null references public.captures(id) on delete cascade,
  media_item_id uuid not null references public.media_items(id) on delete cascade,
  primary key (capture_id, media_item_id)
);

create table public.activity_checkins (
  id uuid primary key default gen_random_uuid(),
  activity_id uuid not null references public.activities(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  entry_id uuid references public.diary_entries(id) on delete set null,
  local_date date not null,
  milestone text not null,
  note text,
  status public.checkin_status not null default 'approved',
  created_at timestamptz not null default now(),
  unique (activity_id, local_date)
);

create table public.checkin_media (
  checkin_id uuid not null references public.activity_checkins(id) on delete cascade,
  media_item_id uuid not null references public.media_items(id) on delete cascade,
  primary key (checkin_id, media_item_id)
);

create table public.drafts (
  id uuid primary key default gen_random_uuid(),
  entry_id uuid not null references public.diary_entries(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  run_id text not null unique,
  payload jsonb not null,
  agent_version text not null,
  version integer not null check (version > 0),
  status public.draft_status not null default 'ready_for_review',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index drafts_one_ready_per_entry on public.drafts(entry_id) where status = 'ready_for_review';

create table public.device_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  expo_push_token text not null unique,
  platform public.device_platform not null,
  last_seen_at timestamptz not null default now(),
  revoked_at timestamptz
);

create table public.notification_preferences (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  timezone text not null default 'UTC',
  diary_enabled boolean not null default false,
  diary_reminder_time time,
  activity_enabled boolean not null default false,
  activity_reminder_time time,
  weekly_recap_enabled boolean not null default false,
  weekly_recap_day smallint check (weekly_recap_day between 1 and 7),
  weekly_recap_time time
);

create table public.weekly_recaps (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  week_start_date date not null,
  payload jsonb not null,
  status public.recap_status not null default 'ready_for_review',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, week_start_date)
);

create table public.provenance (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  entry_id uuid references public.diary_entries(id) on delete cascade,
  checkin_id uuid references public.activity_checkins(id) on delete cascade,
  field_path text not null,
  source_type public.provenance_source not null,
  media_item_id uuid references public.media_items(id) on delete set null,
  created_at timestamptz not null default now(),
  check (entry_id is not null or checkin_id is not null)
);

create index diary_entries_user_date_idx on public.diary_entries(user_id, local_date desc);
create index activities_user_status_idx on public.activities(user_id, status);
create index captures_user_date_idx on public.captures(user_id, local_date desc);
create index media_items_user_idx on public.media_items(user_id);
create index activity_checkins_activity_date_idx on public.activity_checkins(activity_id, local_date desc);
create index activity_checkins_user_idx on public.activity_checkins(user_id);
create index drafts_user_entry_idx on public.drafts(user_id, entry_id);
create index provenance_user_idx on public.provenance(user_id);

create or replace function public.set_updated_at()
returns trigger language plpgsql as $$ begin new.updated_at = now(); return new; end; $$;

create trigger profiles_set_updated_at before update on public.profiles for each row execute function public.set_updated_at();
create trigger diary_entries_set_updated_at before update on public.diary_entries for each row execute function public.set_updated_at();
create trigger activities_set_updated_at before update on public.activities for each row execute function public.set_updated_at();
create trigger captures_set_updated_at before update on public.captures for each row execute function public.set_updated_at();
create trigger drafts_set_updated_at before update on public.drafts for each row execute function public.set_updated_at();
create trigger weekly_recaps_set_updated_at before update on public.weekly_recaps for each row execute function public.set_updated_at();

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, display_name, timezone)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'display_name', ''), coalesce(new.raw_user_meta_data ->> 'timezone', 'UTC'));
  insert into public.notification_preferences (user_id, timezone)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'timezone', 'UTC'));
  return new;
end;
$$;

create trigger on_auth_user_created after insert on auth.users for each row execute procedure public.handle_new_user();

insert into storage.buckets (id, name, public) values ('dayfora-media', 'dayfora-media', false)
on conflict (id) do update set public = false;

grant usage on schema public to authenticated;
grant select, insert, update, delete on all tables in schema public to authenticated;

alter table public.profiles enable row level security;
alter table public.diary_entries enable row level security;
alter table public.activities enable row level security;
alter table public.captures enable row level security;
alter table public.media_items enable row level security;
alter table public.entry_media enable row level security;
alter table public.capture_media enable row level security;
alter table public.activity_checkins enable row level security;
alter table public.checkin_media enable row level security;
alter table public.drafts enable row level security;
alter table public.device_tokens enable row level security;
alter table public.notification_preferences enable row level security;
alter table public.weekly_recaps enable row level security;
alter table public.provenance enable row level security;

create policy "profiles are private" on public.profiles for all to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);
create policy "entries are private" on public.diary_entries for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "activities are private" on public.activities for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "captures are private" on public.captures for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id and (requested_activity_id is null or exists (select 1 from public.activities a where a.id = requested_activity_id and a.user_id = (select auth.uid()))));
create policy "media is private" on public.media_items for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "drafts are private" on public.drafts for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "device tokens are private" on public.device_tokens for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "notification preferences are private" on public.notification_preferences for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "weekly recaps are private" on public.weekly_recaps for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "provenance is private" on public.provenance for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

create policy "entry media follows entry ownership" on public.entry_media for all to authenticated
using (exists (select 1 from public.diary_entries e where e.id = entry_id and e.user_id = (select auth.uid())))
with check (exists (select 1 from public.diary_entries e where e.id = entry_id and e.user_id = (select auth.uid())) and exists (select 1 from public.media_items m where m.id = media_item_id and m.user_id = (select auth.uid())));
create policy "capture media follows capture ownership" on public.capture_media for all to authenticated
using (exists (select 1 from public.captures c where c.id = capture_id and c.user_id = (select auth.uid())))
with check (exists (select 1 from public.captures c where c.id = capture_id and c.user_id = (select auth.uid())) and exists (select 1 from public.media_items m where m.id = media_item_id and m.user_id = (select auth.uid())));
create policy "checkins are private" on public.activity_checkins for all to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id and exists (select 1 from public.activities a where a.id = activity_id and a.user_id = (select auth.uid())) and (entry_id is null or exists (select 1 from public.diary_entries e where e.id = entry_id and e.user_id = (select auth.uid()))));
create policy "checkin media follows checkin ownership" on public.checkin_media for all to authenticated
using (exists (select 1 from public.activity_checkins c where c.id = checkin_id and c.user_id = (select auth.uid())))
with check (exists (select 1 from public.activity_checkins c where c.id = checkin_id and c.user_id = (select auth.uid())) and exists (select 1 from public.media_items m where m.id = media_item_id and m.user_id = (select auth.uid())));

create policy "users read their private media" on storage.objects for select to authenticated
using (bucket_id = 'dayfora-media' and (storage.foldername(name))[1] = 'users' and (storage.foldername(name))[2] = (select auth.uid()::text));
create policy "users upload their private media" on storage.objects for insert to authenticated
with check (bucket_id = 'dayfora-media' and (storage.foldername(name))[1] = 'users' and (storage.foldername(name))[2] = (select auth.uid()::text));
create policy "users update their private media" on storage.objects for update to authenticated
using (bucket_id = 'dayfora-media' and (storage.foldername(name))[1] = 'users' and (storage.foldername(name))[2] = (select auth.uid()::text))
with check (bucket_id = 'dayfora-media' and (storage.foldername(name))[1] = 'users' and (storage.foldername(name))[2] = (select auth.uid()::text));
create policy "users delete their private media" on storage.objects for delete to authenticated
using (bucket_id = 'dayfora-media' and (storage.foldername(name))[1] = 'users' and (storage.foldername(name))[2] = (select auth.uid()::text));
