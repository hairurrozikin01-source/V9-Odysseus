"""READ-ONLY paper account simulator for completed V9 1h signals.

This module never connects to an exchange or places orders. It estimates a
conservative paper ledger from V9's historical signal outcomes.
"""
import argparse
import json
import os
from datetime import datetime, timezone

HISTORY_FILE = ".v9-state/v9_signal_history.json"
OUTPUT_FILE = "paper_trading_report.json"
HORIZON = "1h"
HORIZON_MS = 60 * 60 * 1000


def _number(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def simulate(
    history,
    initial_capital=1_000_000,
    allocation_pct=10.0,
    fee_pct_per_side=0.1,
    slippage_pct_per_side=0.05,
):
    """Simulate one non-overlapping BUY/SELL position at a time."""
    if not isinstance(history, list):
        raise ValueError("Signal history must be a list.")
    if initial_capital <= 0:
        raise ValueError("Initial capital must be positive.")
    if not 0 < allocation_pct <= 100:
        raise ValueError("Allocation percentage must be in (0, 100].")
    if fee_pct_per_side < 0 or slippage_pct_per_side < 0:
        raise ValueError("Fee and slippage assumptions cannot be negative.")

    cost_pct = 2 * (fee_pct_per_side + slippage_pct_per_side)
    balance = float(initial_capital)
    peak = balance
    max_drawdown_pct = 0.0
    next_available_ms = 0
    trades = []
    pending = 0
    skipped_overlap = 0
    invalid = 0

    candidates = sorted(
        history,
        key=lambda item: int(item.get("entry_time_ms", 0))
        if isinstance(item, dict) else 0,
    )

    for signal in candidates:
        if not isinstance(signal, dict):
            invalid += 1
            continue
        validation = signal.get("validation")
        result = validation.get(HORIZON) if isinstance(validation, dict) else None
        if not isinstance(result, dict):
            invalid += 1
            continue

        status = result.get("status")
        if status == "PENDING":
            pending += 1
            continue
        if status not in {"POSITIVE", "NEGATIVE", "NEUTRAL"}:
            invalid += 1
            continue

        try:
            entry_time_ms = int(signal.get("entry_time_ms"))
        except (TypeError, ValueError):
            invalid += 1
            continue
        entry_price = _number(signal.get("entry_price"))
        exit_price = _number(result.get("exit_price"))
        direction = signal.get("direction", "BUY")
        if entry_price is None or exit_price is None or direction not in {"BUY", "SELL"}:
            invalid += 1
            continue

        if entry_time_ms < next_available_ms:
            skipped_overlap += 1
            continue

        gross_pct = ((exit_price - entry_price) / entry_price) * 100
        if direction == "SELL":
            gross_pct *= -1
        net_pct = gross_pct - cost_pct
        notional = balance * (allocation_pct / 100)
        pnl = notional * (net_pct / 100)
        balance += pnl
        next_available_ms = entry_time_ms + HORIZON_MS

        peak = max(peak, balance)
        drawdown = ((peak - balance) / peak) * 100 if peak else 0.0
        max_drawdown_pct = max(max_drawdown_pct, drawdown)

        trades.append({
            "symbol": signal.get("symbol", "UNKNOWN"),
            "entry_time_ms": entry_time_ms,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "direction": direction,
            "notional": round(notional, 2),
            "gross_return_pct": round(gross_pct, 4),
            "estimated_cost_pct": round(cost_pct, 4),
            "net_return_pct": round(net_pct, 4),
            "pnl": round(pnl, 2),
            "balance_after": round(balance, 2),
            "outcome": "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "FLAT"),
        })

    wins = sum(1 for trade in trades if trade["pnl"] > 0)
    losses = sum(1 for trade in trades if trade["pnl"] < 0)
    decided = wins + losses
    net_profit = balance - float(initial_capital)

    return {
        "version": "V9-PAPER-1.0",
        "mode": "PAPER ONLY - READ ONLY",
        "real_orders_enabled": False,
        "exchange_connection_enabled": False,
        "assumptions": {
            "initial_capital_idr": round(float(initial_capital), 2),
            "allocation_per_trade_pct": allocation_pct,
            "fee_pct_per_side": fee_pct_per_side,
            "slippage_pct_per_side": slippage_pct_per_side,
            "round_trip_cost_pct": round(cost_pct, 4),
            "exit_horizon": HORIZON,
            "max_concurrent_positions": 1,
        },
        "summary": {
            "completed_trades": len(trades),
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(wins / decided * 100, 2) if decided else None,
            "pending_signals": pending,
            "skipped_overlapping_signals": skipped_overlap,
            "invalid_records": invalid,
            "initial_capital_idr": round(float(initial_capital), 2),
            "ending_balance_idr": round(balance, 2),
            "net_profit_idr": round(net_profit, 2),
            "net_return_pct": round(net_profit / float(initial_capital) * 100, 4),
            "max_drawdown_pct": round(max_drawdown_pct, 4),
        },
        "trades": trades,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "disclaimer": (
            "Paper simulation only. Historical signal outcomes do not guarantee "
            "future performance. Fees/slippage are estimates; this is not a live "
            "broker or exchange account and does not establish achievable returns."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="V9 read-only paper trading simulator")
    parser.add_argument("--capital", type=float, default=1_000_000)
    parser.add_argument("--allocation-pct", type=float, default=10.0)
    parser.add_argument("--fee-per-side-pct", type=float, default=0.1)
    parser.add_argument("--slippage-per-side-pct", type=float, default=0.05)
    parser.add_argument("--history", default=HISTORY_FILE)
    parser.add_argument("--output", default=OUTPUT_FILE)
    args = parser.parse_args()

    if os.path.exists(args.history):
        with open(args.history, "r", encoding="utf-8") as handle:
            history = json.load(handle)
    else:
        history = []

    report = simulate(
        history,
        initial_capital=args.capital,
        allocation_pct=args.allocation_pct,
        fee_pct_per_side=args.fee_per_side_pct,
        slippage_pct_per_side=args.slippage_per_side_pct,
    )
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    print(json.dumps(report["summary"], indent=2))
    print("PAPER ONLY - NO EXCHANGE CONNECTION OR REAL ORDERS")


if __name__ == "__main__":
    main()
