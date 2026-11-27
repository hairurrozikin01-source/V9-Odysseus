# V9.7.1 Approval Inbox API — Development Slice

**Status: development / authenticated middleware required / READ ONLY with respect to broker execution.**

This branch adds an owner-only human decision endpoint to the existing local SQLite review service. It does not implement login, sessions, identity verification, CSRF token issuance, hosting, or broker integration.

## Trusted middleware contract

Before exposing the WSGI app, a trusted server-side authentication middleware must set:
- `REMOTE_USER`: stable authenticated actor ID
- `v9.authenticated`: boolean `True`
- `v9.role`: `owner` or `viewer`

For POST decision requests, a trusted CSRF middleware must additionally set `v9.csrf_valid=True` only after validating the request's CSRF token. These WSGI values must be set by server middleware, never copied from browser-controlled headers, query parameters, or JSON. Do not expose the WSGI app directly to the public internet.

## Routes

- `GET /api/v1/transaction-control/status`: reports MANUAL_APPROVAL and explicit hard blocks while execution is unavailable.
- `GET /api/v1/proposals?status=PROPOSAL_PENDING&limit=50`: lists sanitized proposal snapshots.
- `GET /api/v1/proposals/{proposal_id}`: returns the exact proposal hash and safe details.
- `POST /api/v1/proposals/{proposal_id}/decision`: owner-only decision record.
- `GET /api/v1/audit/events?limit=50`: read-only audit events.

Decision JSON must contain exactly `action` (`APPROVE` or `REJECT`) and `proposal_hash` (64 lowercase hexadecimal characters). The actor is derived from trusted middleware. Request bodies are capped at 4 KiB. The decision is bound to the exact proposal hash and expiry. Viewer, unauthenticated, missing-CSRF, malformed, stale, or expired requests fail closed.

## Safety boundary

- APPROVED means the human reviewed and approved that exact proposal snapshot; it does not place or queue an order.
- `orders_enabled` and `execution_enabled` remain false in every response.
- Status reports `EXECUTION_NOT_IMPLEMENTED`, `BROKER_NOT_CONNECTED`, and `LIVE_TRADING_DISABLED` as hard blocks.
- No Exness credentials, order API, or automatic execution is added.
- Odysseus remains independent and read-only.

## Validation

Run `python -m unittest discover -s tests -v` with Python 3.12. CI validates automated code paths only; it does not validate a production identity provider, deployment configuration, TLS, CSRF middleware, database operations, or live trading.
