# V9 Approval Inbox API Contract

Status: design contract only — not a deployed or callable HTTP API.

This contract describes how a future Web App/PWA and Android client may communicate with a hosted V9 review service. The current `TransactionReviewService` is a local synchronous Python service; it has no HTTP routes, database, authentication middleware, or broker connectivity.

## Design rules

- Default mode is `MANUAL_APPROVAL`; `AUTOMATIC_EXECUTION` remains unavailable and locked.
- All endpoints require authenticated owner/session identity. Never trust an `actor` supplied only by the request body; derive it from the authenticated session.
- All writes require a unique idempotency key and server-generated UTC timestamps.
- The server stores an immutable proposal snapshot and its canonical hash. A client must submit the hash it reviewed.
- A failed or unavailable data, risk, or audit gate returns a blocked result. No manual action can override a hard block.
- Approval records consent to the exact proposal only. It does not create, queue, or submit a broker order.
- No broker credentials, passwords, OTPs, API secrets, or full account identifiers may be returned to or stored by the client.
- Every state transition is written to an append-only audit facility before success is returned. If audit persistence fails, the operation fails closed.
- Responses must not claim an order was sent or filled. There is no order endpoint in this contract.

## Proposed endpoints

### `GET /api/v1/transaction-control/status`

Returns current review mode and safety availability.

Example response:

```json
{
  "mode": "MANUAL_APPROVAL",
  "execution_available": false,
  "orders_enabled": false,
  "new_risk_allowed": false,
  "hard_blocks": [],
  "server_time": "2026-11-26T14:00:00Z"
}
```

### `GET /api/v1/proposals?status=PROPOSAL_PENDING`

Returns a paginated list of proposals visible to the authenticated owner. List items contain proposal ID, symbol, side, timeframe, created/expiry timestamps, status, proposal hash, and a compact reason summary. Sensitive account data is excluded.

### `GET /api/v1/proposals/{proposal_id}`

Returns the immutable reviewed snapshot, proposal hash, data/risk/audit gate results, expiry, and audit history references. The client must display the complete material risk information before enabling the approve/reject action.

### `POST /api/v1/proposals`

Creates a proposal from trusted server-side V9 outputs. The client must not be allowed to set `data_ok`, `risk_ok`, `audit_ok`, estimated risk, or other safety gate results. Those are derived and validated by the server.

Example request:

```json
{
  "candidate_id": "candidate-opaque-id",
  "client_request_id": "uuid-generated-by-client"
}
```

Possible results: `PROPOSAL_PENDING` or `BLOCKED`. A blocked proposal remains non-actionable.

### `POST /api/v1/proposals/{proposal_id}/decision`

Records a human decision on the exact proposal version. The authenticated server session supplies the actor identity.

Example request:

```json
{
  "action": "APPROVE",
  "proposal_hash": "sha256-hex-digest",
  "idempotency_key": "uuid-generated-by-client"
}
```

Allowed actions: `APPROVE`, `REJECT`.

Possible results: `APPROVED`, `REJECTED`, `EXPIRED`, or `BLOCKED`. If the hash differs from the stored proposal hash, return `BLOCKED` and require a fresh proposal. An expired proposal cannot be approved. Repeating an identical idempotent request returns the original decision record; it must not create a second transition.

### `GET /api/v1/audit/events`

Returns paginated, read-only audit events for the authenticated owner, with event ID, timestamp, event type, proposal ID, state, actor reference, and integrity-verification status. It must never expose secrets.

## Error model

- `400 INVALID_REQUEST`: malformed request.
- `401 UNAUTHENTICATED`: missing/invalid session.
- `403 FORBIDDEN`: authenticated identity lacks permission.
- `404 NOT_FOUND`: proposal does not exist or is not visible.
- `409 STATE_CONFLICT`: proposal is no longer pending or idempotency conflict.
- `410 EXPIRED`: proposal review window elapsed.
- `422 PROPOSAL_CHANGED`: submitted hash does not match immutable snapshot.
- `423 BLOCKED`: a hard safety gate failed.
- `503 AUDIT_UNAVAILABLE`: audit write/verification unavailable; no success transition is committed.

## Security and operational requirements before implementation

1. Use TLS, secure session management, CSRF protection for cookie sessions, rate limits, and server-side authorization.
2. Keep broker credentials in a separate secrets manager/service. The Approval Inbox API must not return them to clients.
3. Store proposal state transactionally with audit writes or use a transactional outbox so a successful decision cannot exist without its audit event.
4. Enforce unique idempotency keys and optimistic concurrency on proposal version/hash.
5. Add retention, backup, restore, key management, alerting, and incident-response procedures for audit records.
6. Add integration tests for concurrent approvals, retries, replay, session expiry, audit outage, and stale proposal data.
7. Conduct independent security review before exposing the API publicly.

## Current implementation boundary

The API above is not implemented. The current Python review service is local and synchronous; proposal state is passed by the caller rather than stored in a database. The local hash-chain journal is useful for development integrity checks but is not a substitute for signed, access-controlled, backed-up production audit storage. No Exness connection, order routing, or automatic execution is enabled.
