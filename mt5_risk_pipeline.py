"""V9 read-only orchestration for MT5 analysis and risk checks.

This pipeline joins validated Exness MT5 exports, technical watch analysis,
position-risk estimation, and the portfolio policy gate. It never places orders.
All account and open-position values are caller-supplied and must be verified.
"""
from datetime import datetime, timezone

from mt5_readonly_adapter import normalize_export, SnapshotValidationError
from mt5_strategy import analyze_snapshot
from risk_calculator import calculate_position_risk, RiskCalculationError
from portfolio_risk_gate import evaluate_portfolio_risk

VERSION = "V9-MT5-RISK-PIPELINE-0.1.0"


def _blocked(status, reason, *, symbol=None, analysis=None, sizing=None, gate=None):
    return {
        "version": VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "reason": reason,
        "symbol": symbol,
        "analysis": analysis,
        "position_risk": sizing,
        "portfolio_gate": gate,
        "mode": "READ ONLY",
        "orders_enabled": False,
        "new_risk_allowed": False,
        "automated_trade_instruction": False,
        "human_review_required": True,
    }


def evaluate_candidate_pipeline(
    *,
    raw_export,
    candidate,
    account,
    open_positions,
    policy=None,
):
    """Evaluate one explicitly supplied candidate; missing inputs fail closed.

    candidate keys: position_id, symbol, side, entry_price, stop_loss_price,
    risk_pct, currency_exposure; optional commission_per_lot_round_turn and
    slippage_ticks_per_lot. Account and open_positions use the risk-gate schema.
    """
    try:
        export = normalize_export(raw_export)
        if not isinstance(candidate, dict):
            raise ValueError("candidate must be an object")
        if not isinstance(account, dict):
            raise ValueError("account must be an object")
        if not isinstance(open_positions, list):
            raise ValueError("open_positions must be a list")

        symbol = candidate.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("candidate.symbol is required")
        symbol = symbol.strip().upper()
        snapshot = next(
            (item for item in export["snapshots"] if item["symbol"] == symbol),
            None,
        )
        if snapshot is None:
            raise ValueError("candidate symbol is absent from the validated MT5 export")

        account_currency = export["account_currency"]
        if str(account.get("currency", "")).upper() != account_currency:
            raise ValueError("account currency must match the validated MT5 export")
        equity = account.get("equity")
        analysis = analyze_snapshot(snapshot)
        side = str(candidate.get("side", "")).upper()
        expected_status = "BULLISH_WATCH" if side == "BUY" else (
            "BEARISH_WATCH" if side == "SELL" else None
        )
        if expected_status is None:
            raise ValueError("candidate.side must be BUY or SELL")
        if analysis.get("status") != expected_status:
            return _blocked(
                "BLOCKED_NO_MATCHING_WATCH",
                "Technical watch status does not match the candidate side.",
                symbol=symbol,
                analysis=analysis,
            )

        position_id = candidate.get("position_id")
        if not isinstance(position_id, str) or not position_id.strip():
            raise ValueError("candidate.position_id is required")
        exposures = candidate.get("currency_exposure")
        if not isinstance(exposures, dict) or not exposures:
            raise ValueError("candidate.currency_exposure must be a non-empty object")

        sizing = calculate_position_risk(
            symbol_metadata=snapshot["symbol_metadata"],
            side=side,
            entry_price=candidate.get("entry_price"),
            stop_loss_price=candidate.get("stop_loss_price"),
            equity=equity,
            risk_pct=candidate.get("risk_pct"),
            account_currency=account_currency,
            commission_per_lot_round_turn=candidate.get(
                "commission_per_lot_round_turn", 0.0
            ),
            slippage_ticks_per_lot=candidate.get("slippage_ticks_per_lot", 0.0),
        )
        if sizing.get("status") == "BLOCKED_BELOW_MIN_VOLUME":
            return _blocked(
                "BLOCKED_BELOW_MIN_VOLUME",
                sizing.get("reason", "Calculated volume is below broker minimum."),
                symbol=symbol,
                analysis=analysis,
                sizing=sizing,
            )

        combined_positions = list(open_positions)
        combined_positions.append({
            "position_id": position_id,
            "risk_amount": sizing["estimated_stop_risk_account_currency"],
            "currency_exposure": exposures,
        })
        gate = evaluate_portfolio_risk(account, combined_positions, policy)
        if gate["status"] != "WITHIN_LIMITS":
            return _blocked(
                "BLOCKED_PORTFOLIO_RISK",
                "Portfolio risk policy blocked the candidate.",
                symbol=symbol,
                analysis=analysis,
                sizing=sizing,
                gate=gate,
            )

        return {
            "version": VERSION,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "WATCH_AND_RISK_CHECK_PASSED",
            "reason": (
                "Technical watch and supplied risk inputs passed configured checks. "
                "This is not trade approval."
            ),
            "symbol": symbol,
            "analysis": analysis,
            "position_risk": sizing,
            "portfolio_gate": gate,
            "mode": "READ ONLY",
            "orders_enabled": False,
            "new_risk_allowed": False,
            "automated_trade_instruction": False,
            "human_review_required": True,
            "limitations": [
                "Account equity, daily loss, open positions, and currency exposures are supplied externally and are not broker-verified.",
                "Candidate entry, stop loss, commission, slippage, and currency exposure require human verification.",
                "No margin check, live account connection, trade authorization, or order execution exists.",
                "A passed check is not a recommendation to trade and does not guarantee execution price or maximum realized loss.",
            ],
        }
    except (ValueError, TypeError, KeyError, SnapshotValidationError,
            RiskCalculationError) as exc:
        return _blocked(
            "BLOCKED_INVALID_OR_MISSING_INPUT",
            str(exc),
            symbol=(candidate.get("symbol") if isinstance(candidate, dict) else None),
        )
