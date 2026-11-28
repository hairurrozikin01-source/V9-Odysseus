# V9.10 Read-Only Backend Integration

## Scope

This integration publishes the existing V9 crypto scanner output and the existing
operational data-quality risk report to Supabase. It does not place orders, connect
to a broker, access wallets, or calculate portfolio exposure.

The Edge Function accepts only reports explicitly marked `READ ONLY`. It validates
signal fields, de-duplicates each symbol/timeframe/entry timestamp, writes signals
using the server-side Supabase service role, and records an operational risk
assessment for provisioned owner accounts.

The `risk_assessments` rows are operational data-quality assessments. They are
not portfolio-risk calculations or trading permissions.

## Required secrets and deployment (manual owner action)

1. In Supabase Dashboard for project `kiwyczhesgrrjwgbvzwk`, open
   **Edge Functions → Secrets** and add `V9_INGEST_KEY` with a newly generated,
   high-entropy random value. Do not paste the value into chat or commit it.
2. In GitHub repository **Settings → Secrets and variables → Actions → New
   repository secret**, add:
   - `V9_INGEST_KEY`: exactly the same value as the Supabase Edge Function secret.
   - `V9_INGEST_URL`: `https://kiwyczhesgrrjwgbvzwk.supabase.co/functions/v1/v9-readonly-ingest`
3. Supabase Edge Functions provide `SUPABASE_URL` and
   `SUPABASE_SERVICE_ROLE_KEY` to the runtime. The service-role key must never
   be added to GitHub, Flutter, or this repository.
4. Deploy the function from the Supabase project using the reviewed source at
   `supabase/functions/v9-readonly-ingest/index.ts`. JWT gateway verification
   is disabled only because this is a server-to-server endpoint; the function
   itself requires the private `x-v9-ingest-key` header and fails closed if absent.

Until both GitHub Actions secrets and the Supabase function secret are configured,
the publisher safely skips or the endpoint rejects the request. The actual secret
configuration status has not been independently verified by this repository change.
Never share the ingest key in screenshots or chat.

## Data mapping

- V9 scanner results → `market_signals` (crypto, 15m, BUY, score as confidence).
- V9 risk monitor → `risk_assessments` for owner accounts.
- Operational levels map as BLOCKED→CRITICAL/BLOCK,
  CAUTION→MEDIUM/REDUCE_RISK, OBSERVE→LOW/ALLOW_REVIEW.
- Every risk row states that it is operational data quality, not portfolio exposure.

## Release gates

Run tests and CI on the development branch, configure secrets through the owner
account, deploy the Edge Function, then confirm a successful scheduled/manual V9
run and verify the resulting rows in Supabase. Only after that should the Flutter
app be rebuilt to show live records.

Passing unit tests alone does not verify deployment, credentials, database writes,
or end-to-end ingestion.
