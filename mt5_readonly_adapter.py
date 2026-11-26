"""V9 MT5 read-only data normalization foundation.

This module does not connect to MT5 and cannot place orders. It validates
snapshots exported by a future, separately controlled MT5 read-only adapter.
"""
from datetime import datetime, timezone
import math

VERSION = "V9-MT5-READONLY-0.1.0"
MODE = "READ ONLY"
SUPPORTED_MARKET_TYPES = {"FOREX", "METAL"}


class SnapshotValidationError(ValueError):
    """Raised when MT5 market data cannot be trusted."""


def _number(value, field, *, positive=False, non_negative=False):
    if isinstance(value, bool):
        raise SnapshotValidationError(f"{field} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise SnapshotValidationError(f"{field} must be numeric")
    if not math.isfinite(result):
        raise SnapshotValidationError(f"{field} must be finite")
    if positive and result <= 0:
        raise SnapshotValidationError(f"{field} must be positive")
    if non_negative and result < 0:
        raise SnapshotValidationError(f"{field} must be non-negative")
    return result


def _utc_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        raise SnapshotValidationError("timestamp_utc is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise SnapshotValidationError("timestamp_utc must be ISO-8601")
    if parsed.tzinfo is None:
        raise SnapshotValidationError("timestamp_utc must include timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_symbol(raw):
    if not isinstance(raw, dict):
        raise SnapshotValidationError("symbol metadata must be an object")
    symbol = raw.get("symbol")
    market_type = raw.get("market_type")
    if not isinstance(symbol, str) or not symbol.strip():
        raise SnapshotValidationError("symbol is required")
    if market_type not in SUPPORTED_MARKET_TYPES:
        raise SnapshotValidationError("market_type must be FOREX or METAL")

    digits = raw.get("digits")
    if isinstance(digits, bool) or not isinstance(digits, int) or not 0 <= digits <= 12:
        raise SnapshotValidationError("digits must be an integer from 0 to 12")

    volume_min = _number(raw.get("volume_min"), "volume_min", positive=True)
    volume_max = _number(raw.get("volume_max"), "volume_max", positive=True)
    volume_step = _number(raw.get("volume_step"), "volume_step", positive=True)
    if volume_min > volume_max:
        raise SnapshotValidationError("volume_min cannot exceed volume_max")

    normalized = {
        "symbol": symbol.strip().upper(),
        "market_type": market_type,
        "base_currency": str(raw.get("base_currency", "")).upper(),
        "quote_currency": str(raw.get("quote_currency", "")).upper(),
        "digits": digits,
        "point": _number(raw.get("point"), "point", positive=True),
        "tick_size": _number(raw.get("tick_size"), "tick_size", positive=True),
        "tick_value": _number(raw.get("tick_value"), "tick_value", positive=True),
        "contract_size": _number(raw.get("contract_size"), "contract_size", positive=True),
        "volume_min": volume_min,
        "volume_max": volume_max,
        "volume_step": volume_step,
        "trade_allowed": raw.get("trade_allowed") is True,
        "source": "MT5",
        "mode": MODE,
    }
    if not normalized["base_currency"] or not normalized["quote_currency"]:
        raise SnapshotValidationError("base_currency and quote_currency are required")
    return normalized


def normalize_tick(raw):
    if not isinstance(raw, dict):
        raise SnapshotValidationError("tick must be an object")
    bid = _number(raw.get("bid"), "bid", positive=True)
    ask = _number(raw.get("ask"), "ask", positive=True)
    if ask < bid:
        raise SnapshotValidationError("ask cannot be below bid")
    timestamp = _utc_timestamp(raw.get("timestamp_utc"))
    return {
        "bid": bid,
        "ask": ask,
        "spread_price": round(ask - bid, 12),
        "timestamp_utc": timestamp,
        "source": "MT5",
        "mode": MODE,
    }


def normalize_candles(raw_candles):
    if not isinstance(raw_candles, list) or not raw_candles:
        raise SnapshotValidationError("candles must be a non-empty list")
    result = []
    previous_time = None
    for index, candle in enumerate(raw_candles):
        if not isinstance(candle, dict):
            raise SnapshotValidationError(f"candle {index} must be an object")
        timestamp = _utc_timestamp(candle.get("timestamp_utc"))
        parsed_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if previous_time is not None and parsed_time <= previous_time:
            raise SnapshotValidationError("candle timestamps must be strictly increasing")
        previous_time = parsed_time
        open_price = _number(candle.get("open"), f"candles[{index}].open", positive=True)
        high = _number(candle.get("high"), f"candles[{index}].high", positive=True)
        low = _number(candle.get("low"), f"candles[{index}].low", positive=True)
        close = _number(candle.get("close"), f"candles[{index}].close", positive=True)
        volume = _number(candle.get("tick_volume"), f"candles[{index}].tick_volume", non_negative=True)
        if high < max(open_price, close, low) or low > min(open_price, close, high):
            raise SnapshotValidationError(f"candle {index} has inconsistent OHLC values")
        result.append({
            "timestamp_utc": timestamp,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "tick_volume": volume,
        })
    return result


def normalize_snapshot(raw):
    """Normalize a broker-exported snapshot; fail closed on any invalid field."""
    if not isinstance(raw, dict):
        raise SnapshotValidationError("snapshot must be an object")
    if raw.get("mode") != MODE:
        raise SnapshotValidationError("snapshot mode must be READ ONLY")
    if raw.get("broker") != "Exness":
        raise SnapshotValidationError("broker must be Exness")
    if raw.get("platform") != "MT5":
        raise SnapshotValidationError("platform must be MT5")
    if raw.get("account_type") != "Raw Spread":
        raise SnapshotValidationError("account_type must be Raw Spread")

    symbol = normalize_symbol(raw.get("symbol_metadata"))
    tick = normalize_tick(raw.get("tick"))
    candles = normalize_candles(raw.get("candles"))
    if raw.get("symbol") != symbol["symbol"]:
        raise SnapshotValidationError("snapshot symbol does not match metadata symbol")

    return {
        "version": VERSION,
        "broker": "Exness",
        "account_type": "Raw Spread",
        "platform": "MT5",
        "mode": MODE,
        "symbol": symbol["symbol"],
        "symbol_metadata": symbol,
        "tick": tick,
        "candles": candles,
        "orders_enabled": False,
        "wallet_access": False,
        "broker_credentials_required": False,
        "automated_trade_instruction": False,
        "limitations": [
            "This module validates exported market data only; it does not connect to MT5.",
            "No order placement or account access is implemented.",
            "Tick value and contract specifications must be confirmed against the live broker symbol.",
            "A validated snapshot is not a trading signal or risk approval."
        ],
    }
