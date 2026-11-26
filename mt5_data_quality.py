"""V9 read-only MT5 market-data quality checks.

This module scores snapshot integrity and broker tradability metadata only.
It does not infer session state, create trade signals, approve risk, or place orders.
"""
from datetime import datetime
import math

VERSION = "V9-MT5-DATA-QUALITY-0.1.0"


def _finite(value, field, *, positive=False):
    if isinstance(value, bool):
        raise ValueError("{} must be numeric".format(field))
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("{} must be numeric".format(field))
    if not math.isfinite(number) or (positive and number <= 0):
        raise ValueError("{} must be finite{}".format(
            field, " and positive" if positive else ""))
    return number


def _time(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("{} is required".format(field))
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("{} must be ISO-8601".format(field)) from exc
    if parsed.tzinfo is None:
        raise ValueError("{} must include timezone".format(field))
    return parsed


def assess_snapshot_quality(snapshot, exported_at_utc,
                            max_spread_atr_ratio=0.15,
                            max_quote_candle_atr=5.0):
    """Return PASS/WARN/BLOCK findings for one already-normalized snapshot."""
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object")
    if snapshot.get("mode") != "READ ONLY" or snapshot.get("orders_enabled") is not False:
        raise ValueError("snapshot must be explicitly READ ONLY with orders disabled")
    if snapshot.get("broker") != "Exness" or snapshot.get("platform") != "MT5":
        raise ValueError("snapshot must originate from Exness MT5")

    spread_limit = _finite(max_spread_atr_ratio, "max_spread_atr_ratio", positive=True)
    deviation_limit = _finite(max_quote_candle_atr, "max_quote_candle_atr", positive=True)
    exported = _time(exported_at_utc, "exported_at_utc")
    tick = snapshot.get("tick")
    candles = snapshot.get("candles")
    metadata = snapshot.get("symbol_metadata")
    if not isinstance(tick, dict) or not isinstance(candles, list) or not candles:
        raise ValueError("tick, candles, and symbol_metadata are required")
    if not isinstance(metadata, dict):
        raise ValueError("symbol_metadata must be an object")

    bid = _finite(tick.get("bid"), "tick.bid", positive=True)
    ask = _finite(tick.get("ask"), "tick.ask", positive=True)
    if ask < bid:
        raise ValueError("ask cannot be below bid")
    tick_time = _time(tick.get("timestamp_utc"), "tick.timestamp_utc")
    tick_age = (exported - tick_time).total_seconds()
    if tick_age < -5:
        raise ValueError("tick timestamp is later than export time")
    if tick_age > 120:
        raise ValueError("tick is stale")

    point = _finite(metadata.get("point"), "symbol_metadata.point", positive=True)
    digits = metadata.get("digits")
    if isinstance(digits, bool) or not isinstance(digits, int) or not 0 <= digits <= 12:
        raise ValueError("symbol_metadata.digits must be an integer from 0 to 12")
    last_close = _finite(candles[-1].get("close"), "last candle close", positive=True)
    high = _finite(candles[-1].get("high"), "last candle high", positive=True)
    low = _finite(candles[-1].get("low"), "last candle low", positive=True)
    if high < low:
        raise ValueError("last candle OHLC range is invalid")

    findings = []
    blocked = False
    warnings = []

    for label, price in (("bid", bid), ("ask", ask), ("last_close", last_close)):
        rounded = round(price, digits)
        if abs(price - rounded) > max(point * 1e-6, 1e-10):
            blocked = True
            findings.append({
                "severity": "BLOCK",
                "code": "PRICE_DIGITS_MISMATCH",
                "field": label,
                "message": "Price precision is inconsistent with broker digits."
            })

    if metadata.get("trade_allowed") is not True:
        blocked = True
        findings.append({
            "severity": "BLOCK",
            "code": "SYMBOL_NOT_TRADE_ALLOWED",
            "message": "Broker metadata does not mark this symbol as tradable."
        })

    # Compare the current mid quote with the latest completed candle close.
    # This is an anomaly screen, not a prediction or execution-price guarantee.
    atr = None
    true_ranges = []
    previous_close = None
    for candle in candles:
        c_high = _finite(candle.get("high"), "candle.high", positive=True)
        c_low = _finite(candle.get("low"), "candle.low", positive=True)
        c_close = _finite(candle.get("close"), "candle.close", positive=True)
        if c_high < c_low:
            raise ValueError("candle high cannot be below low")
        tr = c_high - c_low if previous_close is None else max(
            c_high - c_low, abs(c_high - previous_close),
            abs(c_low - previous_close))
        true_ranges.append(tr)
        previous_close = c_close
    if len(true_ranges) >= 14:
        atr = sum(true_ranges[-14:]) / 14.0
    if atr is None or atr <= 0:
        warnings.append("ATR could not be calculated from at least 14 candles.")
    else:
        quote_deviation = abs(((bid + ask) / 2.0) - last_close) / atr
        if quote_deviation > deviation_limit:
            blocked = True
            findings.append({
                "severity": "BLOCK",
                "code": "QUOTE_CANDLE_DEVIATION",
                "deviation_atr": round(quote_deviation, 6),
                "message": "Current quote is unusually far from the latest candle close."
            })

        spread_ratio = (ask - bid) / atr
        if spread_ratio > spread_limit:
            blocked = True
            findings.append({
                "severity": "BLOCK",
                "code": "SPREAD_TOO_WIDE",
                "spread_atr_ratio": round(spread_ratio, 6),
                "limit": spread_limit,
                "message": "Spread exceeds the configured spread-to-ATR quality limit."
            })

    if warnings:
        findings.extend({
            "severity": "WARN", "code": "INSUFFICIENT_QUALITY_CONTEXT",
            "message": warning
        } for warning in warnings)

    status = "BLOCKED" if blocked else ("WARNING" if warnings else "PASS")
    return {
        "version": VERSION,
        "symbol": snapshot.get("symbol"),
        "status": status,
        "findings": findings,
        "metrics": {
            "tick_age_seconds": round(tick_age, 3),
            "spread_price": round(ask - bid, digits),
            "atr_14": round(atr, digits) if atr is not None else None,
        },
        "mode": "READ ONLY",
        "orders_enabled": False,
        "new_risk_allowed": False,
        "automated_trade_instruction": False,
        "human_review_required": True,
        "limitations": [
            "Quality checks do not establish whether the market session is open.",
            "A PASS result is not a trading signal, risk approval, or trade authorization.",
            "The quality thresholds require calibration using verified Exness demo data."
        ]
    }


def assess_export_quality(export, max_spread_atr_ratio=0.15,
                          max_quote_candle_atr=5.0):
    if not isinstance(export, dict) or export.get("mode") != "READ ONLY":
        raise ValueError("export must be explicitly READ ONLY")
    snapshots = export.get("snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        raise ValueError("export snapshots must be a non-empty list")
    results = [
        assess_snapshot_quality(
            item, export.get("exported_at_utc"),
            max_spread_atr_ratio=max_spread_atr_ratio,
            max_quote_candle_atr=max_quote_candle_atr)
        for item in snapshots
    ]
    return {
        "version": VERSION,
        "broker": "Exness",
        "account_type": "Raw Spread",
        "platform": "MT5",
        "mode": "READ ONLY",
        "snapshot_count": len(results),
        "blocked_count": sum(item["status"] == "BLOCKED" for item in results),
        "warning_count": sum(item["status"] == "WARNING" for item in results),
        "results": results,
        "orders_enabled": False,
        "new_risk_allowed": False,
        "automated_trade_instruction": False,
    }
