# V9–Odysseus

**Status: development / READ ONLY.** V9 is not approved for live trading.

V9 is the trading and risk engine. Odysseus is the read-only oversight layer for market analysis, data-quality checks, signal audits, risk monitoring, and reporting.

## Product scope

- Gold (XAUUSD) and Forex symbols actually available and validated on the connected Exness MT5 account.
- Existing crypto analysis and SHIB Hunter as separate market-analysis modules.
- Mobile-first dashboard in Indonesian.
- Capital Protection First + Adaptive Profit Growth.

## Current architecture

| Component | Responsibility | Current boundary |
|---|---|---|
| V9 Engine | Market scans and signal generation | Analysis only |
| MT5 Read-Only Adapter | Validate exported MT5 quotes, candles, and symbol metadata | No MT5 connection or orders from GitHub Actions |
| Risk Monitor | Inspect available reports and configured risk flags | Not yet a live portfolio/drawdown risk engine |
| Odysseus | Audit reports and system health | Read-only; no broker credentials |
| SHIB Hunter | Multi-chain token discovery | Read-only; no automatic purchases |
| Mobile Dashboard | Display generated reports | Static report viewer, not a live terminal |

## Running with an Android phone

The repository can be maintained from GitHub in a mobile browser or the GitHub app. GitHub Actions runs the Python checks and generates downloadable report artifacts.

1. Open the repository's **Actions** tab.
2. Open the latest successful **V9 Odysseus Engine** run.
3. Download the `v9-odysseus-reports-<run_id>` artifact.
4. Extract the ZIP on the phone and open `v9_dashboard.html` in a browser.

The dashboard reflects the data available when that workflow ran. A successful Actions run proves only that the automated software checks completed; it does not prove live market connectivity or profitability.

## Exness MT5 integration status

The MQL5 exporter in `mt5/ExnessReadOnlyExporter.mq5` is intended to export a read-only snapshot named `v9_mt5_readonly_snapshot.json` from a Windows MT5 terminal. `mt5_quality_report.py` validates and scores the export before the dashboard is built. If no export file is present in a workflow run, the report explicitly shows `DATA_NOT_AVAILABLE`; it never invents market data. The Python adapter validates the exported JSON. GitHub Actions on Linux cannot compile or run the MQL5 exporter and does not connect to an MT5 terminal.

A Windows MT5/MetaEditor environment is still required to compile and test the exporter against an Exness demo account. Do not share MT5 passwords, investor passwords, API keys, or account secrets in GitHub issues or chat.

## Safety gates before any execution

1. Compile and verify the exporter in MetaEditor.
2. Validate real demo-account snapshots, symbol specifications, quote freshness, spreads, and candle integrity.
3. Complete Gold/Forex strategy tests with realistic spread, commission, swap, and slippage.
4. Validate combined exposure, daily-loss limits, drawdown limits, fail-closed behavior, and emergency stop.
5. Complete demo forward testing and review operational failures.
6. Obtain explicit user approval for any separately designed execution feature.

Until all gates pass, V9 remains READ ONLY. No live orders, automatic buying, or guaranteed returns are supported or promised.
