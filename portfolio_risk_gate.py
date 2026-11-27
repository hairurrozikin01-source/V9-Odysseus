"""V9 read-only portfolio risk policy gate.

Consumes already-calculated risk amounts from a trusted upstream calculator.
It does not calculate lots, convert currencies, connect to a broker, or place orders.
Missing or invalid inputs fail closed.
"""
import math
from datetime import datetime, timezone

VERSION = "V9-PORTFOLIO-RISK-GATE-0.1.0"
DEFAULT_MAX_RISK_PER_TRADE_PCT = 1.0
DEFAULT_MAX_DAILY_LOSS_PCT = 3.0
DEFAULT_MAX_OPEN_RISK_PCT = 5.0
DEFAULT_MAX_CURRENCY_CONCENTRATION_PCT = 3.0


def _finite_number(value, field, *, positive=False, non_negative=False):
    if isinstance(value, bool):
        raise ValueError("{} must be numeric".format(field))
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("{} must be numeric".format(field))
    if not math.isfinite(number):
        raise ValueError("{} must be finite".format(field))
    if positive and number <= 0:
        raise ValueError("{} must be positive".format(field))
    if non_negative and number < 0:
        raise ValueError("{} must be non-negative".format(field))
    return number


def evaluate_portfolio_risk(account, positions, policy=None):
    """Evaluate a supplied risk snapshot; return a gate, never an order."""
    if not isinstance(account, dict):
        raise ValueError("account must be an object")
    if not isinstance(positions, list):
        raise ValueError("positions must be a list")
    policy = policy or {}
    if not isinstance(policy, dict):
        raise ValueError("policy must be an object")

    limits = {
        "max_risk_per_trade_pct": _finite_number(
            policy.get("max_risk_per_trade_pct", DEFAULT_MAX_RISK_PER_TRADE_PCT),
            "max_risk_per_trade_pct", positive=True),
        "max_daily_loss_pct": _finite_number(
            policy.get("max_daily_loss_pct", DEFAULT_MAX_DAILY_LOSS_PCT),
            "max_daily_loss_pct", positive=True),
        "max_open_risk_pct": _finite_number(
            policy.get("max_open_risk_pct", DEFAULT_MAX_OPEN_RISK_PCT),
            "max_open_risk_pct", positive=True),
        "max_currency_concentration_pct": _finite_number(
            policy.get("max_currency_concentration_pct", DEFAULT_MAX_CURRENCY_CONCENTRATION_PCT),
            "max_currency_concentration_pct", positive=True),
    }
    equity = _finite_number(account.get("equity"), "account.equity", positive=True)
    daily_loss_amount = _finite_number(
        account.get("daily_loss_amount"), "account.daily_loss_amount", non_negative=True)
    if daily_loss_amount > equity:
        raise ValueError("daily_loss_amount cannot exceed equity")

    daily_loss_pct = daily_loss_amount / equity * 100.0
    flags = []
    critical = False
    if daily_loss_pct >= limits["max_daily_loss_pct"]:
        critical = True
        flags.append({
            "severity": "CRITICAL",
            "code": "DAILY_LOSS_LIMIT_REACHED",
            "message": "Daily loss limit reached; block new risk.",
        })

    total_open_risk_amount = 0.0
    currency_exposure_amounts = {}
    seen_ids = set()
    for index, position in enumerate(positions):
        if not isinstance(position, dict):
            raise ValueError("positions[{}] must be an object".format(index))
        position_id = position.get("position_id")
        if not isinstance(position_id, str) or not position_id.strip():
            raise ValueError("positions[{}].position_id is required".format(index))
        if position_id in seen_ids:
            raise ValueError("duplicate position_id: {}".format(position_id))
        seen_ids.add(position_id)

        risk_amount = _finite_number(
            position.get("risk_amount"), "positions[{}].risk_amount".format(index),
            non_negative=True)
        total_open_risk_amount += risk_amount
        risk_pct = risk_amount / equity * 100.0
        if risk_pct > limits["max_risk_per_trade_pct"]:
            critical = True
            flags.append({
                "severity": "CRITICAL",
                "code": "POSITION_RISK_LIMIT_EXCEEDED",
                "position_id": position_id,
                "risk_pct": round(risk_pct, 4),
                "message": "Position risk exceeds the configured per-trade limit.",
            })

        exposures = position.get("currency_exposure")
        if not isinstance(exposures, dict):
            raise ValueError(
                "positions[{}].currency_exposure must be an object".format(index))
        for currency, amount in exposures.items():
            if not isinstance(currency, str) or not currency.strip():
                raise ValueError("currency exposure keys must be non-empty strings")
            value = _finite_number(
                amount, "currency_exposure.{}".format(currency), non_negative=True)
            currency_exposure_amounts[currency.upper()] = (
                currency_exposure_amounts.get(currency.upper(), 0.0) + value
            )

    total_open_risk_pct = total_open_risk_amount / equity * 100.0
    if total_open_risk_pct >= limits["max_open_risk_pct"]:
        critical = True
        flags.append({
            "severity": "CRITICAL",
            "code": "TOTAL_OPEN_RISK_LIMIT_REACHED",
            "risk_pct": round(total_open_risk_pct, 4),
            "message": "Combined open risk reached or exceeded the configured limit.",
        })

    concentration = {
        currency: amount / equity * 100.0
        for currency, amount in currency_exposure_amounts.items()
    }
    for currency, percentage in concentration.items():
        if percentage >= limits["max_currency_concentration_pct"]:
            critical = True
            flags.append({
                "severity": "CRITICAL",
                "code": "CURRENCY_CONCENTRATION_LIMIT_REACHED",
                "currency": currency,
                "exposure_pct": round(percentage, 4),
                "message": "Currency concentration reached or exceeded the configured limit.",
            })

    status = "BLOCKED" if critical else "WITHIN_LIMITS"
    return {
        "version": VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "READ ONLY",
        "status": status,
        "summary": (
            "New risk must be blocked until limits and inputs are reviewed."
            if critical else
            "Supplied values are within configured policy limits; this is not trade approval."
        ),
        "account": {
            "equity": equity,
            "daily_loss_amount": daily_loss_amount,
            "daily_loss_pct": round(daily_loss_pct, 4),
        },
        "portfolio": {
            "open_position_count": len(positions),
            "total_open_risk_amount": round(total_open_risk_amount, 8),
            "total_open_risk_pct": round(total_open_risk_pct, 4),
            "currency_concentration_pct": {
                key: round(value, 4) for key, value in concentration.items()
            },
        },
        "limits": limits,
        "flags": flags,
        "safety": {
            "new_risk_allowed": False,
            "orders_enabled": False,
            "wallet_access": False,
            "broker_credentials_required": False,
            "automated_trade_instruction": False,
        },
        "limitations": [
            "Risk amounts and currency exposures must be calculated and verified upstream.",
            "This gate does not calculate lot size, pip value, conversion rates, margin, or stop distance.",
            "This gate does not read live account equity, open positions, or broker data.",
            "WITHIN_LIMITS is not trade approval and does not authorize new positions.",
        ],
    }
