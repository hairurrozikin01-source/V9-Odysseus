# V9–Odysseus Transaction Control Center

Status: design specification only. This document does not enable broker connectivity or order execution.

## Product decisions

- Platforms: responsive Web App/PWA and Android.
- Interface: Indonesian language, dark theme, mobile-first.
- Markets in scope: Gold (XAUUSD) and eligible Forex symbols available from the connected Exness MT5 account.
- Default transaction mode: MANUAL_APPROVAL.
- Optional mode: AUTOMATIC_EXECUTION, locked until all release gates are met and the owner explicitly enables it.
- Capital policy: V9 Adaptive Capital Protection — Capital Protection First + Adaptive Profit Growth.
- Odysseus remains an independent read-only oversight and audit layer and must not hold broker credentials.

## Control modes

### MANUAL_APPROVAL (default)

1. V9 creates a candidate proposal from validated market data.
2. Risk checks and Odysseus audit run independently.
3. The proposal is shown for human review with symbol, side, timeframe, entry context, stop/invalidating level, estimated volume, estimated monetary risk, spread, data timestamp, strategy version, and risk/audit findings.
4. The owner can approve or reject. Approval is bound to the exact proposal version and expires after a configurable short validity period.
5. Any material change in quote, spread, size, stop, risk result, or proposal version invalidates approval and requires a new review.
6. A rejection is recorded and cannot be silently retried as an approval.

### AUTOMATIC_EXECUTION (locked)

This mode is unavailable until every release gate below has been independently verified. When eventually enabled, it must still obey the same risk limits, data-quality checks, audit trail, and emergency stop. A mode toggle alone must never bypass a failed safety gate.

## Fail-closed state model

- DISABLED: no execution capability.
- READ_ONLY: market analysis and reports only.
- PROPOSAL_PENDING: proposal awaiting human review.
- APPROVED: exact proposal approved, but not yet sent.
- EXECUTION_PENDING: execution request queued after all final checks.
- EXECUTED: broker confirms an order identifier and fill details.
- REJECTED: owner or policy rejected the proposal.
- EXPIRED: approval or proposal validity elapsed.
- BLOCKED: data, risk, audit, broker, or system checks failed.
- UNKNOWN: execution outcome cannot be confirmed; halt new orders and reconcile broker state before retrying.

Only explicit, authenticated transitions are permitted. Never treat an API timeout as proof that an order failed; use UNKNOWN and reconcile to prevent duplicate orders.

## Mandatory safety invariants

- Orders are disabled in the current implementation.
- No broker password, investor password, OTP, API secret, or account identifier is stored in this module or committed to the repository.
- Odysseus is read-only and cannot submit or modify orders.
- Missing, stale, malformed, crossed, or inconsistent market data blocks new execution.
- Missing account equity, open-position data, currency exposure, contract specifications, or cost assumptions blocks sizing and execution.
- Risk limits are hard limits, not suggestions. A manual approval cannot override a BLOCKED result.
- Any material proposal change invalidates prior approval.
- Duplicate submission protection and broker reconciliation are required before any live execution feature.
- Emergency stop blocks all new orders; position-closing behavior must be designed and tested separately.
- Every state transition records timestamp, actor, proposal hash/version, policy version, reason, and broker correlation ID where applicable. Secrets must never enter logs.

## Required screens

1. **Dashboard** — engine/data status, current mode, market coverage, risk status, pending approvals, latest audit events.
2. **Mode & Safety** — Manual Approval selected by default; Automatic shown as locked with unmet prerequisites; emergency stop status.
3. **Approval Inbox** — proposal summary, data freshness, spread/cost assumptions, risk in account currency and percentage, Odysseus findings, expiry, approve/reject actions.
4. **Proposal Detail** — complete immutable proposal snapshot and explanation of each check.
5. **Execution History** — proposal, approver, state transitions, broker acknowledgement/fill, rejection or block reason.
6. **Audit & System Health** — data-quality, risk, adapter, broker connection, and policy-version status.

## Automatic-mode release gates

1. MQL5 exporter compiled and tested in MetaEditor on an Exness demo account.
2. Real demo snapshots validated for symbol metadata, tick freshness, spread, candles, volume steps, tick-value currency, and account currency.
3. Strategy backtests and out-of-sample tests include spread, commission, swap, slippage, and realistic execution assumptions.
4. Portfolio exposure, daily loss, drawdown, margin, correlated exposure, and fail-closed controls tested.
5. Demo forward testing completed with reconnect, timeout, duplicate-request, partial-fill, rejection, and unknown-outcome scenarios.
6. Independent code/security review and operational runbook completed.
7. Owner explicitly enables automatic execution after reviewing the risks and test evidence.

Passing GitHub Actions unit tests alone does not satisfy these gates.

## Current implementation boundary

This is a product and safety specification. The existing dashboard is a static report viewer; the MT5 exporter is not yet compiled or validated on Windows. No live broker connection, order submission, approval API, or automatic execution is implemented by this document.
