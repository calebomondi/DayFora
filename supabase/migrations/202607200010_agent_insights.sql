create type public.agent_insight_status as enum ('active', 'dismissed', 'kept');
create type public.agent_insight_type as enum ('pattern', 'continuity', 'comeback');

create table public.agent_insights (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  insight_type public.agent_insight_type not null,
  body text not null check (char_length(trim(body)) > 0),
  source_refs jsonb not null default '{}'::jsonb,
  status public.agent_insight_status not null default 'active',
  eligible_after timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index agent_insights_user_status_idx
  on public.agent_insights(user_id, status, created_at desc);

create trigger agent_insights_set_updated_at
before update on public.agent_insights
for each row execute function public.set_updated_at();

grant select, insert, update, delete on public.agent_insights to authenticated;
alter table public.agent_insights enable row level security;

create policy "agent insights are private" on public.agent_insights for all to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);
