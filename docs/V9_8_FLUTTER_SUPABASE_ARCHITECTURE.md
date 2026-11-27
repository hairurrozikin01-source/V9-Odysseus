# V9.8 — Flutter + Supabase Application Foundation

**Status:** architecture approved; implementation in development  
**Branch:** `v9.8-flutter-supabase-foundation`

## Approved platform decisions

- Flutter is the shared client for Android and Web.
- Supabase Auth is the identity provider.
- Supabase Postgres is the application data store.
- The Python V9 engine remains a separate service; the Flutter client must not contain trading logic or broker credentials.
- Odysseus remains an independent, read-only oversight layer.
- Transaction Control Center is a review interface. An APPROVE decision records human review only; it does not place or queue an order.

## Initial application slice

The first Flutter slice provides:
1. A configuration check that fails closed when Supabase URL or publishable key is absent.
2. Email/password sign-in for provisioned users.
3. An authenticated landing page with explicit READ ONLY status.
4. Sign-out.
5. No public sign-up, no broker connection, no wallet connection, and no order endpoint.

User accounts should initially be provisioned by the project owner through the Supabase dashboard. Do not enable public self-registration until account lifecycle, abuse controls, and role assignment are reviewed.

## Identity and authorization rules

- Supabase Auth authenticates the user and issues JWT access tokens.
- Application roles are assigned only through a trusted server-side process. Never trust a role, user ID, or owner flag supplied by Flutter, browser storage, request JSON, or arbitrary user-editable metadata.
- Default role is viewer / read-only. Owner privileges must be explicitly granted and verified server-side.
- The Python Approval Inbox API must independently verify Supabase JWT signature, issuer, audience, expiry, and subject before creating its trusted principal. Use the project's JWKS endpoint for asymmetric signing keys where configured; do not decode JWTs without signature verification.
- Keep the API fail-closed. No valid identity means no access.
- Apply Row Level Security (RLS) to every user-facing database table and grant only the minimum required SQL privileges.
- Never put Supabase secret/service-role keys, Exness credentials, MT5 passwords, Telegram bot tokens, or other server secrets in Flutter, Git, or client-side build artifacts.
- A Supabase publishable key is designed for client use, but it is not an authorization mechanism; RLS and server-side checks remain mandatory.

## Data boundary

Supabase stores app identity and application data. It does not become the broker execution engine. The Flutter app must not connect directly to Exness or MT5. The V9 service owns market analysis and risk evaluation. Odysseus receives the minimum data required for audit and monitoring and remains read-only.

## Release gates

Before any production deployment:
- Review RLS policies and database grants table by table.
- Verify JWTs server-side and test invalid, expired, wrong-issuer, and wrong-audience tokens.
- Define owner provisioning and recovery procedures.
- Add rate limits, secure hosting, TLS, monitoring, backups, and audit retention.
- Review session persistence and deep-link redirects for Android and Web.
- Complete security tests for authorization and CSRF where cookie-based sessions are used.
- Keep broker integration and order execution disabled until separate demo testing, risk validation, and explicit owner approval.

## Current limitations

This foundation is not a production-ready authentication deployment. It does not create a Supabase project, configure email delivery, provision users, create database tables, or connect the Flutter client to the Python API. CI success will validate only the code paths included in that workflow.
