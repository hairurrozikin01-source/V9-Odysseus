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

## Read-only technical watch analyzer

The development branch now includes `mt5_strategy.py`, a technical-context analyzer that consumes normalized Exness MT5 snapshots. It calculates EMA(9), EMA(21), RSI(14), ATR(14), and spread-to-ATR ratio, then labels each symbol as BULLISH_WATCH, BEARISH_WATCH, NO_SETUP, BLOCKED_WIDE_SPREAD, or INSUFFICIENT_DATA.

This is a watch-list foundation only. It does not produce an executable entry, stop-loss, take-profit, lot size, portfolio risk approval, or order. Its default spread filter is a configurable engineering threshold and must be calibrated with broker demo data before any strategy evaluation. The analyzer is covered by unit tests and is automatically included by unittest discovery.

## Read-only portfolio risk policy gate

The branch now includes `portfolio_risk_gate.py`. It evaluates externally supplied account equity, daily loss, per-position risk amounts, and currency exposure amounts against configurable policy limits. Conservative defaults are 1% maximum risk per position, 3% daily loss, 5% combined open risk, and 3% currency concentration.

The gate fails closed for missing or malformed required inputs and blocks when a configured threshold is reached or exceeded. It deliberately does not calculate lot size, pip value, conversion rates, margin, or stop distance; those require a separately validated broker-aware calculator. It does not connect to Exness, read live positions, approve trades, or allow new risk. Even a WITHIN_LIMITS result is informational only.

## Read-only MT5 position risk calculator

The branch now includes `risk_calculator.py`. It estimates a theoretical volume from entry price, stop-loss price, account equity, requested risk percentage, and MT5 tick/volume specifications. It floors volume to the broker volume step, respects the broker maximum, and blocks when the calculated volume is below the broker minimum. Optional round-turn commission and slippage allowances reduce the theoretical volume.

The exporter now includes the MT5 account deposit currency and labels the exported tick value with that currency. The normalizer and calculator reject missing or mismatched currency labels. This metadata assertion still requires verification against a real Exness demo terminal and the broker's symbol specification. Commission, slippage, swap, spread changes, gaps, conversion changes, and execution conditions may cause realized loss to exceed the estimate. The calculator does not calculate margin, read live account equity, derive tick value, convert currencies, or place orders. It always returns READ ONLY output and requires human review.

## Current implementation status

- Existing V9 crypto engine and SHIB Hunter remain separate from the MT5 market adapter.
- MT5 normalized snapshot validation and a read-only technical watch analyzer are implemented on the V9.6 development branch; actual MT5 data capture and MetaEditor compilation remain unverified.
- A read-only portfolio risk policy gate and unit tests are added; it consumes supplied risk/exposure amounts and is not yet connected to live account or position data.
- A read-only MT5 position risk calculator and unit tests are added. The MQL5 exporter now labels tick value with account currency; the adapter and calculator reject currency mismatches. Actual Exness metadata, commission, and symbol-specific volume constraints still require demo-terminal verification.
- Odysseus and Risk Monitor are rule-based/read-only foundations, not a fully autonomous AI agent or complete portfolio risk platform.
- V9.5.2 Risk Monitor CI passed in GitHub Actions Run #52. That confirms the tested software workflow, not trading performance or live readiness.

## Read-only MT5 risk orchestration pipeline

The branch now includes `mt5_risk_pipeline.py`, which orchestrates the validated multi-symbol export, per-symbol technical watch analysis, broker-metadata position-risk estimate, and portfolio risk gate for one explicitly supplied candidate. It requires the candidate side to match the technical watch status, and requires the caller to supply account currency, account equity/daily loss, existing open-position risk, and candidate currency exposure. Missing or invalid inputs fail closed.

A result of `WATCH_AND_RISK_CHECK_PASSED` means only that the supplied snapshot and supplied risk inputs passed these software checks. It is not trade approval, an order intent, or a recommendation to trade. The pipeline always returns `orders_enabled: false`, `new_risk_allowed: false`, and `automated_trade_instruction: false`. Account and exposure inputs are not independently read from or verified by Exness. GitHub Actions Run #91 completed successfully: the unit-test step, V9 run, SHIB Hunter multi-chain radar, Odysseus read-only audit, Risk Monitor, mobile dashboard build, and artifact upload all passed. The workflow artifact is `v9-odysseus-reports-45807219592`. This validates the CI software workflow only; it does not validate trading performance or live broker connectivity. Validation with real Exness demo-terminal exports and MetaEditor compilation remain pending.


## V9.7 read-only MT5 market-data quality checks

The development branch now includes `mt5_data_quality.py` and automated tests. It checks quote freshness against export time, broker price precision, symbol tradability metadata, spread relative to ATR, and unusually large deviation between the current mid quote and the latest completed candle close. It produces per-symbol PASS, WARNING, or BLOCKED findings and an aggregate multi-symbol report.

These checks are conservative data-quality filters only. They do not determine whether a market session is open, infer that a symbol is currently suitable to trade, generate an entry, approve risk, or execute orders. Thresholds must be calibrated against verified Exness demo exports. All outputs remain READ ONLY with orders and new risk disabled.
