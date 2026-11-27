"""V9 read-only broker-aware position risk calculator.

Calculates a conservative theoretical volume from MT5 symbol metadata.
It does not read an account, convert currencies, calculate margin, or place orders.
The MT5 tick_value must already be expressed in the account deposit currency.
"""
import math
from decimal import Decimal, ROUND_FLOOR
from datetime import datetime, timezone

VERSION = "V9-RISK-CALCULATOR-0.1.0"


class RiskCalculationError(ValueError):
    """Raised when required risk inputs are missing or unsafe."""


def _number(value, field, *, positive=False, non_negative=False):
    if isinstance(value, bool):
        raise RiskCalculationError("{} must be numeric".format(field))
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise RiskCalculationError("{} must be numeric".format(field))
    if not math.isfinite(result):
        raise RiskCalculationError("{} must be finite".format(field))
    if positive and result <= 0:
        raise RiskCalculationError("{} must be positive".format(field))
    if non_negative and result < 0:
        raise RiskCalculationError("{} must be non-negative".format(field))
    return result


def _floor_to_step(value, step):
    value_d = Decimal(str(value))
    step_d = Decimal(str(step))
    units = (value_d / step_d).to_integral_value(rounding=ROUND_FLOOR)
    return float(units * step_d)


def calculate_position_risk(
    *,
    symbol_metadata,
    side,
    entry_price,
    stop_loss_price,
    equity,
    risk_pct,
    account_currency,
    commission_per_lot_round_turn=0.0,
    slippage_ticks_per_lot=0.0,
):
    """Return a risk-budgeted lot estimate; never return an executable order."""
    if not isinstance(symbol_metadata, dict):
        raise RiskCalculationError("symbol_metadata must be an object")

    symbol = symbol_metadata.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        raise RiskCalculationError("symbol is required")
    if symbol_metadata.get("mode") != "READ ONLY":
        raise RiskCalculationError("symbol metadata must be marked READ ONLY")
    if symbol_metadata.get("source") != "MT5":
        raise RiskCalculationError("symbol metadata source must be MT5")
    if not isinstance(account_currency, str) or not account_currency.strip():
        raise RiskCalculationError("account_currency is required")
    tick_value_currency = symbol_metadata.get("tick_value_currency")
    if not isinstance(tick_value_currency, str) or not tick_value_currency.strip():
        raise RiskCalculationError("tick_value_currency is required")
    if tick_value_currency.upper() != account_currency.upper():
        raise RiskCalculationError("tick_value_currency must match account_currency")

    side = str(side).upper()
    if side not in ("BUY", "SELL"):
        raise RiskCalculationError("side must be BUY or SELL")

    entry = _number(entry_price, "entry_price", positive=True)
    stop = _number(stop_loss_price, "stop_loss_price", positive=True)
    account_equity = _number(equity, "equity", positive=True)
    risk_percentage = _number(risk_pct, "risk_pct", positive=True)
    if risk_percentage > 100:
        raise RiskCalculationError("risk_pct cannot exceed 100")

    if side == "BUY" and stop >= entry:
        raise RiskCalculationError("BUY stop loss must be below entry price")
    if side == "SELL" and stop <= entry:
        raise RiskCalculationError("SELL stop loss must be above entry price")

    tick_size = _number(symbol_metadata.get("tick_size"), "tick_size", positive=True)
    tick_value = _number(symbol_metadata.get("tick_value"), "tick_value", positive=True)
    volume_min = _number(symbol_metadata.get("volume_min"), "volume_min", positive=True)
    volume_max = _number(symbol_metadata.get("volume_max"), "volume_max", positive=True)
    volume_step = _number(symbol_metadata.get("volume_step"), "volume_step", positive=True)
    if volume_min > volume_max:
        raise RiskCalculationError("volume_min cannot exceed volume_max")
    if volume_step > volume_max:
        raise RiskCalculationError("volume_step cannot exceed volume_max")

    commission = _number(
        commission_per_lot_round_turn,
        "commission_per_lot_round_turn",
        non_negative=True,
    )
    slippage_ticks = _number(
        slippage_ticks_per_lot,
        "slippage_ticks_per_lot",
        non_negative=True,
    )

    stop_distance = abs(entry - stop)
    stop_ticks = stop_distance / tick_size
    price_risk_per_lot = stop_ticks * tick_value
    slippage_cost_per_lot = slippage_ticks * tick_value
    total_risk_per_lot = (
        price_risk_per_lot + commission + slippage_cost_per_lot
    )
    if not math.isfinite(total_risk_per_lot) or total_risk_per_lot <= 0:
        raise RiskCalculationError("total risk per lot is invalid")

    risk_budget = account_equity * risk_percentage / 100.0
    theoretical_volume = risk_budget / total_risk_per_lot
    capped_volume = min(theoretical_volume, volume_max)
    volume = _floor_to_step(capped_volume, volume_step)

    if volume < volume_min:
        return {
            "version": VERSION,
            "symbol": symbol.strip().upper(),
            "status": "BLOCKED_BELOW_MIN_VOLUME",
            "reason": "Risk budget is too small for the broker minimum volume.",
            "risk_budget_account_currency": round(risk_budget, 8),
            "theoretical_volume_lots": round(theoretical_volume, 8),
            "volume_lots": 0.0,
            "estimated_stop_risk_account_currency": 0.0,
            "mode": "READ ONLY",
            "orders_enabled": False,
            "automated_trade_instruction": False,
        }

    estimated_risk = total_risk_per_lot * volume
    estimated_risk_pct = estimated_risk / account_equity * 100.0
    status = "CAPPED_AT_BROKER_MAX" if theoretical_volume > volume_max else "CALCULATED"

    return {
        "version": VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol.strip().upper(),
        "side": side,
        "status": status,
        "entry_price": entry,
        "stop_loss_price": stop,
        "stop_distance_price": round(stop_distance, 10),
        "stop_distance_ticks": round(stop_ticks, 8),
        "tick_size": tick_size,
        "tick_value_per_lot_account_currency": tick_value,
        "account_currency": account_currency.upper(),
        "price_risk_per_lot_account_currency": round(price_risk_per_lot, 8),
        "commission_per_lot_round_turn_account_currency": commission,
        "slippage_cost_per_lot_account_currency": round(slippage_cost_per_lot, 8),
        "total_risk_per_lot_account_currency": round(total_risk_per_lot, 8),
        "equity_account_currency": account_equity,
        "risk_pct_requested": risk_percentage,
        "risk_budget_account_currency": round(risk_budget, 8),
        "theoretical_volume_lots": round(theoretical_volume, 8),
        "volume_lots": volume,
        "estimated_stop_risk_account_currency": round(estimated_risk, 8),
        "estimated_stop_risk_pct": round(estimated_risk_pct, 6),
        "volume_min": volume_min,
        "volume_max": volume_max,
        "volume_step": volume_step,
        "mode": "READ ONLY",
        "orders_enabled": False,
        "automated_trade_instruction": False,
        "human_review_required": True,
        "limitations": [
            "MT5 tick_value must be verified to be in the account deposit currency.",
            "Commission and slippage are estimates supplied by the caller.",
            "Gaps, spread changes, swaps, currency conversion changes, and execution slippage can increase realized loss.",
            "This is not margin calculation, trade approval, or an order instruction.",
            "No live account, broker, or order connection is implemented.",
        ],
    }
