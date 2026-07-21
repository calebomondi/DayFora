-- Hybrid diary retrieval is additive.  Existing diary/media/activity rows are
-- retained; this table stores only title/body text vectors for approved v1
-- entries and can be rebuilt or removed independently during migration review.
create extension if not exists vector with schema extensions;

create table if not exists public.diary_entry_embeddings (
  entry_id uuid primary key references public.diary_entries(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  content text not null,
  content_hash text not null,
  embedding extensions.vector(384),
  model text not null default 'Supabase/gte-small',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists diary_entry_embeddings_user_idx
  on public.diary_entry_embeddings(user_id, updated_at desc);
create index if not exists diary_entry_embeddings_hnsw_idx
  on public.diary_entry_embeddings using hnsw (embedding vector_ip_ops);

alter table public.diary_entry_embeddings enable row level security;
grant select on public.diary_entry_embeddings to authenticated;
create policy "diary embedding text is private"
  on public.diary_entry_embeddings for select to authenticated
  using ((select auth.uid()) = user_id);

create or replace function public.sync_diary_entry_embedding_source()
returns trigger language plpgsql set search_path = public as $$
declare
  source_text text;
begin
  if new.status = 'approved' and new.v1_saved_at is not null then
    source_text := trim(coalesce(new.title, '') || E'\n' || coalesce(new.body, ''));
    insert into public.diary_entry_embeddings(entry_id, user_id, content, content_hash)
    values (new.id, new.user_id, source_text, md5(source_text))
    on conflict (entry_id) do update
      set user_id = excluded.user_id,
          content = excluded.content,
          content_hash = excluded.content_hash,
          embedding = case
            when public.diary_entry_embeddings.content_hash = excluded.content_hash
            then public.diary_entry_embeddings.embedding
            else null
          end,
          updated_at = now();
  end if;
  return new;
end;
$$;

drop trigger if exists diary_entries_sync_embedding_source on public.diary_entries;
create trigger diary_entries_sync_embedding_source
after insert or update of title, body, status, v1_saved_at on public.diary_entries
for each row execute function public.sync_diary_entry_embedding_source();

create or replace function public.match_diary_entry_embeddings(
  query_embedding extensions.vector(384),
  match_threshold real default 0.45,
  match_count integer default 20,
  requested_user_id uuid default auth.uid()
)
returns table(entry_id uuid, similarity real)
language sql stable security definer set search_path = public, extensions as $$
  select e.entry_id,
         (e.embedding <#> query_embedding) * -1 as similarity
  from public.diary_entry_embeddings e
  join public.diary_entries d on d.id = e.entry_id
  where e.user_id = requested_user_id
    and d.user_id = requested_user_id
    and d.status = 'approved'
    and e.embedding is not null
    and (e.embedding <#> query_embedding) * -1 >= match_threshold
  order by e.embedding <#> query_embedding
  limit greatest(1, least(match_count, 100));
$$;

revoke all on function public.match_diary_entry_embeddings(
  extensions.vector(384), real, integer, uuid
) from public;
grant execute on function public.match_diary_entry_embeddings(
  extensions.vector(384), real, integer, uuid
) to service_role;
