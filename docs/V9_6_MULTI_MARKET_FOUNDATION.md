# V9.6 Multi-Market Foundation — Design Plan

Status: approved development direction; design only. This document does not enable live trading.

## Product scope

V9 is planned to support:
- Gold (XAUUSD).
- Forex currency pairs available from the connected broker/MT5 account.
- Existing crypto analysis modules as a separate market adapter.

"All Forex pairs" means all eligible symbols actually offered by the selected broker and account, after symbol discovery and contract validation. It does not mean every theoretical currency combination is tradable.

## Core architecture

1. **Market Data Adapters**
   - Binance Spot adapter for the existing crypto engine.
   - MT5 read-only adapter for Gold and Forex quotes, candles, symbol metadata, trading sessions, spread, tick size/value, contract size, and volume constraints.
   - Normalize timestamps, OHLCV, symbol identifiers, and data-quality flags without erasing market-specific metadata.

2. **Market Strategy Engines**
   - Gold strategy module for XAUUSD.
   - Forex strategy module operating only on broker-discovered and validated symbols.
   - Each strategy produces an analysis/signal record, not an order.
   - Strategies must account for instrument-specific sessions, spreads, volatility, and contract specifications.

3. **Shared V9 Risk Engine**
   - Calculate risk using instrument-specific tick value, contract size, quote currency, account currency, and broker volume rules.
   - Aggregate exposure across Gold and Forex, including correlated positions and concentration by currency.
   - Enforce configurable per-trade, daily-loss, total-exposure, and drawdown limits.
   - Fail closed when required metadata or prices are missing, stale, inconsistent, or invalid.
   - Risk Engine can veto any proposed transaction.

4. **Odysseus AI oversight**
   - Initially read-only: audit data quality, signals, risk checks, and system health.
   - Must not hold broker credentials or submit orders.
   - Report uncertainty and missing evidence rather than guessing.

5. **Future execution boundary (not implemented)**
   - A separate MT5 Execution Bridge may be designed only after backtesting and paper trading gates pass.
   - It must accept only a validated, risk-approved order intent from V9.
   - Broker credentials must be isolated from Odysseus and never exposed in logs or reports.
   - Require explicit user activation, an emergency stop, duplicate-order protection, reconciliation, and auditable order records.
   - Live order placement remains disabled in this phase.

## Development stages and acceptance gates

### Stage A — MT5 read-only connectivity
- Connect to a demo/read-only MT5 environment.
- Discover broker symbols and normalize symbol metadata.
- Validate quote freshness, missing candles, spread, tick size/value, contract size, trading sessions, and volume constraints.
- No order API calls.

### Stage B — Gold and Forex analysis
- Implement XAUUSD analysis separately from Forex pair analysis.
- Add broker-aware symbol selection and explicit unsupported-symbol handling.
- Test different digits, quote currencies, pip sizes, and contract specifications.

### Stage C — Unified portfolio risk
- Test combined Gold + Forex exposure.
- Test currency concentration and correlated positions.
- Verify that missing or invalid metadata blocks risk approval.
- Verify hard stops and daily-loss limits under simulated scenarios.

### Stage D — Historical testing and paper trading
- Backtest with realistic spread, commission, swap, slippage, and session assumptions.
- Prevent look-ahead bias and data leakage.
- Run demo paper trading across different market conditions.
- Review drawdown, expectancy, profit factor, sample size, and operational failures; do not use win rate alone as a readiness metric.

### Stage E — Separately approved limited execution
- Only after all prior gates pass and the user explicitly approves.
- Start on a demo account, then consider tightly limited live exposure only after separate approval.
- Keep Capital Protection First + Adaptive Profit Growth as a non-negotiable system principle.

## Non-negotiable safety rules

- READ ONLY remains the active mode during V9.6 foundation work.
- No live orders, auto-buy, wallet access, or broker execution in this phase.
- Never claim a strategy is profitable based only on successful software tests.
- No guaranteed returns or promised win rate.
- If market data, broker metadata, or risk calculations cannot be validated, do not issue an executable order intent.
- User approval is required before enabling any live execution capability.

## Current implementation status

- Existing V9 crypto engine and SHIB Hunter remain separate from the planned MT5 market adapter.
- Odysseus and Risk Monitor are rule-based/read-only foundations, not a fully autonomous AI agent or complete portfolio risk platform.
- V9.5.2 Risk Monitor CI passed in GitHub Actions Run #52. That confirms the tested software workflow, not trading performance or live readiness.
