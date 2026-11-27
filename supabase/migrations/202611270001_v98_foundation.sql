-- V9.8 Supabase foundation
-- Apply in Supabase SQL Editor only after reviewing the project ref.
-- Client-side users receive read access only to their own private records.
-- Trusted backend writes operational records using server credentials.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.user_roles (
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner', 'viewer')),
  created_at timestamptz not null default now(),
  primary key (user_id, role)
);

create table if not exists public.market_signals (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  market text not null check (market in ('forex', 'gold', 'crypto', 'other')),
  timeframe text not null,
  direction text not null check (direction in ('BUY', 'SELL', 'NEUTRAL')),
  confidence numeric(5,2) check (confidence between 0 and 100),
  strategy text,
  rationale text,
  signal_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.risk_assessments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  signal_id uuid references public.market_signals(id) on delete set null,
  risk_level text not null check (risk_level in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
  decision text not null check (decision in ('ALLOW_REVIEW', 'REDUCE_RISK', 'BLOCK')),
  rationale text not null,
  assessment_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.trade_reviews (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  signal_id uuid references public.market_signals(id) on delete set null,
  proposal_hash text not null check (proposal_hash ~ '^[a-f0-9]{64}$'),
  decision text not null check (decision in ('APPROVED', 'REJECTED')),
  decision_note text,
  decided_at timestamptz not null default now()
);

create table if not exists public.audit_events (
  id bigint generated always as identity primary key,
  user_id uuid references auth.users(id) on delete set null,
  event_type text not null,
  event_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists market_signals_created_at_idx
  on public.market_signals (created_at desc);
create index if not exists market_signals_symbol_created_at_idx
  on public.market_signals (symbol, created_at desc);
create index if not exists risk_assessments_user_created_at_idx
  on public.risk_assessments (user_id, created_at desc);
create index if not exists trade_reviews_user_decided_at_idx
  on public.trade_reviews (user_id, decided_at desc);
create index if not exists audit_events_user_created_at_idx
  on public.audit_events (user_id, created_at desc);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (user_id, display_name)
  values (new.id, nullif(new.raw_user_meta_data ->> 'display_name', ''))
  on conflict (user_id) do nothing;

  insert into public.user_roles (user_id, role)
  values (new.id, 'viewer')
  on conflict (user_id, role) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

alter table public.profiles enable row level security;
alter table public.user_roles enable row level security;
alter table public.market_signals enable row level security;
alter table public.risk_assessments enable row level security;
alter table public.trade_reviews enable row level security;
alter table public.audit_events enable row level security;

-- Remove broad default access before granting narrow client permissions.
revoke all on public.profiles, public.user_roles, public.market_signals,
  public.risk_assessments, public.trade_reviews, public.audit_events
  from anon, authenticated;

grant select on public.profiles, public.user_roles, public.market_signals,
  public.risk_assessments, public.trade_reviews, public.audit_events
  to authenticated;
grant update (display_name) on public.profiles to authenticated;

create policy "profiles_select_own"
on public.profiles for select to authenticated
using (user_id = (select auth.uid()));

create policy "profiles_update_own"
on public.profiles for update to authenticated
using (user_id = (select auth.uid()))
with check (user_id = (select auth.uid()));

create policy "roles_select_own"
on public.user_roles for select to authenticated
using (user_id = (select auth.uid()));

create policy "signals_read_authenticated"
on public.market_signals for select to authenticated
using (true);

create policy "risk_assessments_select_own"
on public.risk_assessments for select to authenticated
using (user_id = (select auth.uid()));

create policy "trade_reviews_select_own"
on public.trade_reviews for select to authenticated
using (user_id = (select auth.uid()));

create policy "audit_events_select_own_or_owner"
on public.audit_events for select to authenticated
using (
  user_id = (select auth.uid())
  or exists (
    select 1 from public.user_roles r
    where r.user_id = (select auth.uid()) and r.role = 'owner'
  )
);

-- Intentionally no client INSERT/UPDATE/DELETE policies for roles,
-- signals, risk assessments, trade reviews, or audit events.
-- Operational writes must come from a trusted backend only.
