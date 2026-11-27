# V9.8 Supabase Database Setup

## Migration file

Apply `supabase/migrations/202611270001_v98_foundation.sql` in the Supabase SQL Editor for the intended project.

Do not run it against a production database until the project owner confirms the project and reviews the SQL.

## Tables

- `profiles`: user-facing display profile; a new profile is created by an Auth trigger.
- `user_roles`: trusted role assignments; new users receive `viewer` by default.
- `market_signals`: shared signal feed, readable by authenticated users.
- `risk_assessments`: private per-user risk assessment history.
- `trade_reviews`: private human review records; APPROVED is not an order.
- `audit_events`: per-user audit records; an owner may read all audit records.

## Security boundary

- RLS is enabled on every table.
- Anonymous users receive no table privileges.
- Authenticated users can read only their own private records.
- Users can update only their own `profiles.display_name`.
- Client-side writes to roles, signals, risk assessments, trade reviews, and audit events are intentionally unavailable.
- Trusted backend services are responsible for operational writes.
- The Supabase service-role/secret key must never be placed in Flutter, a browser, or a public Git repository.
- The initial Auth trigger assigns `viewer`; owner promotion must be performed through a separate trusted administrative process, never from client metadata.

## Manual verification after applying

1. Confirm all six tables exist in the Supabase Table Editor.
2. Confirm RLS is enabled on all six tables.
3. Create a test user through the Auth dashboard.
4. Confirm the user receives a `profiles` row and a `viewer` role.
5. Sign in as that user and confirm only their own profile, risk, review, and audit rows are visible.
6. Confirm the client cannot insert or modify role assignments or operational records.
7. Do not connect broker execution. It remains disabled.

## Current status

This migration is committed to the V9.8 development branch. It has **not** been applied to a Supabase project, because the project URL and owner confirmation are not yet available.
