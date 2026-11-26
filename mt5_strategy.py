"""Read-only technical context for normalized Exness MT5 snapshots.

This module creates watch candidates only. It does not issue orders or position sizes.
"""
from datetime import datetime, timezone
import math

VERSION = "V9-MT5-ANALYSIS-0.1.0"
MIN_CANDLES = 30
MAX_SPREAD_ATR_RATIO = 0.15


def _ema(values, period):
    if len(values) < period:
        return None
    value = sum(values[:period]) / period
    alpha = 2.0 / (period + 1)
    for item in values[period:]:
        value = alpha * item + (1.0 - alpha) * value
    return value


def _rsi(values, period=14):
    if len(values) <= period:
        return None
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(change, 0.0) for change in changes[-period:]]
    losses = [max(-change, 0.0) for change in changes[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    if avg_gain == 0:
        return 0.0
    relative_strength = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))


def _atr(candles, period=14):
    if len(candles) <= period:
        return None
    true_ranges = []
    previous_close = None
    for candle in candles:
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])
        if previous_close is None:
            true_range = high - low
        else:
            true_range = max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            )
        true_ranges.append(true_range)
        previous_close = close
    return sum(true_ranges[-period:]) / period


def analyze_snapshot(snapshot, max_spread_atr_ratio=MAX_SPREAD_ATR_RATIO):
    """Return a conservative watch-only technical assessment."""
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object")
    if snapshot.get("mode") != "READ ONLY" or snapshot.get("orders_enabled") is not False:
        raise ValueError("snapshot must be explicitly READ ONLY with orders disabled")
    if snapshot.get("broker") != "Exness" or snapshot.get("platform") != "MT5":
        raise ValueError("snapshot must originate from Exness MT5")
    if snapshot.get("account_type") != "Raw Spread":
        raise ValueError("snapshot account type must be Raw Spread")
    if max_spread_atr_ratio <= 0 or not math.isfinite(max_spread_atr_ratio):
        raise ValueError("max_spread_atr_ratio must be a finite positive number")

    candles = snapshot.get("candles")
    tick = snapshot.get("tick")
    symbol = snapshot.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol is required")
    if not isinstance(candles, list) or len(candles) < MIN_CANDLES:
        return {
            "symbol": symbol,
            "status": "INSUFFICIENT_DATA",
            "reason": "At least {} candles are required.".format(MIN_CANDLES),
            "mode": "READ ONLY",
            "orders_enabled": False,
        }
    if not isinstance(tick, dict):
        raise ValueError("tick is required")

    closes = [float(candle["close"]) for candle in candles]
    if any(not math.isfinite(value) or value <= 0 for value in closes):
        raise ValueError("close prices must be finite and positive")

    fast = _ema(closes, 9)
    slow = _ema(closes, 21)
    rsi = _rsi(closes, 14)
    atr = _atr(candles, 14)
    if fast is None or slow is None or rsi is None or atr is None or atr <= 0:
        return {
            "symbol": symbol,
            "status": "INSUFFICIENT_DATA",
            "reason": "Indicators could not be calculated safely.",
            "mode": "READ ONLY",
            "orders_enabled": False,
        }

    bid = float(tick["bid"])
    ask = float(tick["ask"])
    if not math.isfinite(bid) or not math.isfinite(ask) or bid <= 0 or ask < bid:
        raise ValueError("tick bid/ask is invalid")
    spread = ask - bid
    spread_atr_ratio = spread / atr
    bullish = fast > slow and closes[-1] > fast and 50 <= rsi <= 70
    bearish = fast < slow and closes[-1] < fast and 30 <= rsi <= 50
    spread_ok = spread_atr_ratio <= max_spread_atr_ratio

    if not spread_ok:
        status = "BLOCKED_WIDE_SPREAD"
        reason = "Spread is too large relative to ATR for watch qualification."
    elif bullish:
        status = "BULLISH_WATCH"
        reason = "EMA trend and RSI conditions align; human review is required."
    elif bearish:
        status = "BEARISH_WATCH"
        reason = "EMA trend and RSI conditions align; human review is required."
    else:
        status = "NO_SETUP"
        reason = "The configured trend and RSI conditions do not align."

    return {
        "version": VERSION,
        "symbol": symbol,
        "market_type": snapshot.get("symbol_metadata", {}).get("market_type"),
        "status": status,
        "reason": reason,
        "indicators": {
            "ema_9": round(fast, 10),
            "ema_21": round(slow, 10),
            "rsi_14": round(rsi, 2),
            "atr_14": round(atr, 10),
            "spread_price": round(spread, 10),
            "spread_atr_ratio": round(spread_atr_ratio, 6),
        },
        "last_candle_time_utc": candles[-1].get("timestamp_utc"),
        "analyzed_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "READ ONLY",
        "orders_enabled": False,
        "automated_trade_instruction": False,
        "human_review_required": status in ("BULLISH_WATCH", "BEARISH_WATCH"),
        "limitations": [
            "Technical watch only; not an entry instruction or profitability claim.",
            "No position sizing, stop-loss, take-profit, account exposure, or order execution.",
            "Candles must be supplied by a separately validated MT5 export.",
        ],
    }


def analyze_export(export, max_spread_atr_ratio=MAX_SPREAD_ATR_RATIO):
    if not isinstance(export, dict) or export.get("mode") != "READ ONLY":
        raise ValueError("export must be explicitly READ ONLY")
    snapshots = export.get("snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        raise ValueError("export snapshots must be a non-empty list")
    results = [
        analyze_snapshot(item, max_spread_atr_ratio=max_spread_atr_ratio)
        for item in snapshots
    ]
    return {
        "version": VERSION,
        "broker": "Exness",
        "account_type": "Raw Spread",
        "platform": "MT5",
        "mode": "READ ONLY",
        "snapshot_count": len(results),
        "results": results,
        "orders_enabled": False,
        "automated_trade_instruction": False,
    }
