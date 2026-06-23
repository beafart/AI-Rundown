alter table public.sentences
  add column if not exists natural_paraphrase text not null default '',
  add column if not exists key_point text not null default '';
