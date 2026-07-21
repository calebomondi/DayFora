alter table public.captures
  add column if not exists day_feeling text
  check (day_feeling is null or day_feeling in ('loved', 'low', 'mixed', 'quiet'));
