alter table public.diary_entries
  add column day_feeling text null
  check (day_feeling in ('loved', 'low', 'mixed', 'quiet'));
