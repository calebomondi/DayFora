-- DayFora diary-first v1.  This is deliberately additive: legacy activity,
-- capture, draft and processing records remain available for reviewed export.

create type public.diary_mood as enum ('happy_fun', 'sad_dull', 'mixed', 'quiet');
create type public.media_upload_status as enum ('pending', 'uploaded', 'failed', 'deleted');
create type public.recap_type as enum ('weekly', 'monthly', 'custom');

alter table public.diary_entries
  alter column title drop default,
  alter column body drop not null,
  alter column body drop default,
  add column if not exists mood_v1 public.diary_mood,
  add column if not exists v1_saved_at timestamptz;

alter table public.media_items
  add column if not exists upload_status public.media_upload_status not null default 'pending';

create table if not exists public.recaps (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  recap_type public.recap_type not null,
  period_start_date date not null,
  period_end_date date not null check (period_end_date >= period_start_date),
  payload jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, recap_type, period_start_date, period_end_date)
);

create table if not exists public.saved_memories (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  entry_id uuid references public.diary_entries(id) on delete cascade,
  recap_id uuid references public.recaps(id) on delete cascade,
  created_at timestamptz not null default now(),
  check ((entry_id is null) <> (recap_id is null))
);

create index if not exists recaps_user_period_idx on public.recaps(user_id, period_start_date desc);
create index if not exists saved_memories_user_idx on public.saved_memories(user_id, created_at desc);

create or replace function public.diary_entry_v1_valid()
returns trigger language plpgsql set search_path = public as $$
begin
  if new.v1_saved_at is not null then
    if cardinality(regexp_split_to_array(trim(new.title), '\\s+')) > 10 then
      raise exception 'Diary titles may contain at most 10 words';
    end if;
    if trim(coalesce(new.title, '')) = '' then
      raise exception 'A diary title is required';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists diary_entries_v1_valid on public.diary_entries;
create trigger diary_entries_v1_valid before insert or update on public.diary_entries
for each row execute function public.diary_entry_v1_valid();

create trigger recaps_set_updated_at before update on public.recaps
for each row execute function public.set_updated_at();

grant select, insert, update, delete on public.recaps, public.saved_memories to authenticated;
alter table public.recaps enable row level security;
alter table public.saved_memories enable row level security;

create policy "recaps are private" on public.recaps for all to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "saved memories are private" on public.saved_memories for all to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

-- No destructive cleanup is performed here.  Legacy media transcripts,
-- descriptions, captures, drafts, activities and checkpoints are retained.
