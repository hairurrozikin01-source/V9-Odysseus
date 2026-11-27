# V9.8 Supabase Database Setup

## Project
- Supabase project: `V9-Odysseus`
- Region: Southeast Asia (Singapore)
- Project reference is supplied to automation through the GitHub secret `SUPABASE_PROJECT_REF`.
- Do not commit database passwords, access tokens, publishable keys, or secret/service-role keys.

## Migration
- Version: `202611270001`
- File: `supabase/migrations/202611270001_v98_foundation.sql`
- The project owner manually executed this SQL in the Supabase SQL Editor on 2026-11-27.
- The SQL Editor displayed `Success. No rows returned`.
- This confirms the SQL command completed without a reported error. The six tables and RLS settings still require verification in Table Editor.
- Because the migration was applied manually, the remote Supabase migration history must be marked as applied before future automated `db push` operations. Do not run this SQL file a second time just to synchronize migration history.

## Tables
- `profiles`: user-facing display profile; a new profile is created by an Auth trigger.
- `user_roles`: trusted role assignments; new users receive `viewer` by default.
- `market_signals`: shared signal feed, readable by authenticated users.
- `risk_assessments`: private per-user risk assessment history.
- `trade_reviews`: private human review records; APPROVED is not an order.
- `audit_events`: per-user audit records; an owner may read all audit records.

## Security boundary
- RLS is enabled on every table by the migration.
- Anonymous users receive no table privileges.
- Authenticated users can read only their own private records.
- Users can update only their own `profiles.display_name`.
- Client-side writes to roles, signals, risk assessments, trade reviews, and audit events are intentionally unavailable.
- Trusted backend services are responsible for operational writes.
- The Supabase service-role/secret key must never be placed in Flutter, a browser, or a public Git repository.
- The initial Auth trigger assigns `viewer`; owner promotion must be performed through a separate trusted administrative process, never from client metadata.
- Broker execution remains disabled. An approval record is not an instruction to place an order.

## GitHub Actions automation
Workflow: `.github/workflows/supabase-database-delivery.yml`

Add these repository Actions secrets in GitHub Settings -> Secrets and variables -> Actions:
1. `SUPABASE_ACCESS_TOKEN`: a Supabase personal access token.
2. `SUPABASE_DB_PASSWORD`: the database password created for this project.
3. `SUPABASE_PROJECT_REF`: the project reference from the Supabase project URL (the subdomain before `.supabase.co`).

Never paste any of these values into chat, source files, workflow logs, or screenshots. The workflow uses them only as environment secrets.

The workflow is manual and has three modes:
- `verify`: reads remote migration history only.
- `baseline`: records migration `202611270001` as already applied. Run this only after visually confirming all six tables and their RLS policies exist in the intended Supabase project. This changes migration history only; it does not execute the SQL file.
- `deploy`: previews pending migrations, then applies them with Supabase CLI. Use only after reviewing the preview and explicitly choosing this operation.

The workflow is stored on the V9.8 development branch. GitHub's manual workflow dispatch becomes available after the workflow is merged into the repository's default branch. Keep PR #8 unmerged until its CI and security review are complete.

## Verification checklist
1. Confirm all six tables exist in Supabase Table Editor.
2. Confirm RLS is enabled on all six tables.
3. Confirm the remote migration history contains version `202611270001` after the baseline workflow is run.
4. Later, create a test user through the Auth dashboard and confirm the user receives a `profiles` row and a `viewer` role.
5. Sign in as that user and confirm only their own profile, risk, review, and audit rows are visible.
6. Confirm the client cannot insert or modify role assignments or operational records.
7. Do not connect broker execution. It remains disabled.

## Current status
- Supabase project created and reported Healthy.
- Foundation SQL was manually executed and returned `Success. No rows returned`.
- Table-by-table and RLS verification is still pending.
- GitHub Actions workflow and Supabase CLI configuration have been added to the V9.8 development branch.
- Migration history baseline has not yet been recorded.
