create table public.diary_entry_addenda (
  id uuid primary key default gen_random_uuid(),
  entry_id uuid not null references public.diary_entries(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  body text,
  created_at timestamptz not null default now()
);

create table public.addendum_media (
  addendum_id uuid not null references public.diary_entry_addenda(id) on delete cascade,
  media_item_id uuid not null references public.media_items(id) on delete cascade,
  primary key (addendum_id, media_item_id)
);

create index diary_entry_addenda_user_entry_idx
  on public.diary_entry_addenda(user_id, entry_id, created_at);

alter table public.diary_entry_addenda enable row level security;
alter table public.addendum_media enable row level security;

grant select, insert, update, delete on public.diary_entry_addenda, public.addendum_media to authenticated;

create policy "addenda are private" on public.diary_entry_addenda for all to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy "addendum media follows addendum ownership" on public.addendum_media for all to authenticated
using (
  exists (
    select 1 from public.diary_entry_addenda a
    where a.id = addendum_id and a.user_id = (select auth.uid())
  )
)
with check (
  exists (
    select 1 from public.diary_entry_addenda a
    where a.id = addendum_id and a.user_id = (select auth.uid())
  )
  and exists (
    select 1 from public.media_items m
    where m.id = media_item_id and m.user_id = (select auth.uid())
  )
);
