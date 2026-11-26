import unittest

from mt5_risk_pipeline import evaluate_candidate_pipeline


def make_export():
    candles = []
    close = 2000.0
    for index in range(40):
        if index > 0:
            close += -0.1 if index % 4 == 0 else 0.2
        candles.append({
            "timestamp_utc": "2026-11-26T10:{:02d}:00Z".format(index),
            "open": close - 0.1,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "tick_volume": 100,
        })
    return {
        "broker": "Exness",
        "platform": "MT5",
        "account_type": "Raw Spread",
        "account_currency": "USD",
        "mode": "READ ONLY",
        "exported_at_utc": "2026-11-26T11:00:00Z",
        "snapshots": [{
            "symbol": "XAUUSD",
            "symbol_metadata": {
                "symbol": "XAUUSD",
                "market_type": "METAL",
                "base_currency": "XAU",
                "quote_currency": "USD",
                "digits": 2,
                "point": 0.01,
                "tick_size": 0.01,
                "tick_value": 1.0,
                "tick_value_currency": "USD",
                "contract_size": 100,
                "volume_min": 0.01,
                "volume_max": 100.0,
                "volume_step": 0.01,
            },
            "tick": {
                "bid": 2005.7,
                "ask": 2005.71,
                "timestamp_utc": "2026-11-26T10:59:00Z",
            },
            "candles": candles,
        }],
    }


def make_candidate(**overrides):
    candidate = {
        "position_id": "candidate-1",
        "symbol": "XAUUSD",
        "side": "BUY",
        "entry_price": 2005.71,
        "stop_loss_price": 2004.71,
        "risk_pct": 0.5,
        "currency_exposure": {"USD": 10},
    }
    candidate.update(overrides)
    return candidate


class Mt5RiskPipelineTests(unittest.TestCase):
    def setUp(self):
        self.raw_export = make_export()
        self.account = {
            "equity": 10000,
            "daily_loss_amount": 100,
            "currency": "USD",
        }
        self.open_positions = []

    def test_valid_candidate_only_passes_watch_and_risk_checks(self):
        result = evaluate_candidate_pipeline(
            raw_export=self.raw_export,
            candidate=make_candidate(),
            account=self.account,
            open_positions=self.open_positions,
        )
        self.assertEqual(result["status"], "WATCH_AND_RISK_CHECK_PASSED")
        self.assertFalse(result["orders_enabled"])
        self.assertFalse(result["new_risk_allowed"])
        self.assertFalse(result["automated_trade_instruction"])

    def test_missing_account_currency_fails_closed(self):
        account = dict(self.account)
        del account["currency"]
        result = evaluate_candidate_pipeline(
            raw_export=self.raw_export,
            candidate=make_candidate(),
            account=account,
            open_positions=[],
        )
        self.assertEqual(result["status"], "BLOCKED_INVALID_OR_MISSING_INPUT")

    def test_wrong_side_for_analysis_is_blocked(self):
        result = evaluate_candidate_pipeline(
            raw_export=self.raw_export,
            candidate=make_candidate(side="SELL", stop_loss_price=2021.1),
            account=self.account,
            open_positions=[],
        )
        self.assertEqual(result["status"], "BLOCKED_NO_MATCHING_WATCH")
        self.assertFalse(result["orders_enabled"])

    def test_portfolio_daily_loss_limit_blocks_candidate(self):
        account = dict(self.account, daily_loss_amount=300)
        result = evaluate_candidate_pipeline(
            raw_export=self.raw_export,
            candidate=make_candidate(),
            account=account,
            open_positions=[],
        )
        self.assertEqual(result["status"], "BLOCKED_PORTFOLIO_RISK")
        self.assertEqual(result["portfolio_gate"]["status"], "BLOCKED")

    def test_missing_currency_exposure_fails_closed(self):
        candidate = make_candidate(currency_exposure=None)
        result = evaluate_candidate_pipeline(
            raw_export=self.raw_export,
            candidate=candidate,
            account=self.account,
            open_positions=[],
        )
        self.assertEqual(result["status"], "BLOCKED_INVALID_OR_MISSING_INPUT")

    def test_missing_symbol_fails_closed(self):
        result = evaluate_candidate_pipeline(
            raw_export=self.raw_export,
            candidate=make_candidate(symbol="EURUSD"),
            account=self.account,
            open_positions=[],
        )
        self.assertEqual(result["status"], "BLOCKED_INVALID_OR_MISSING_INPUT")

    def test_stale_export_fails_closed(self):
        raw_export = make_export()
        raw_export["exported_at_utc"] = "2026-11-26T12:00:00Z"
        result = evaluate_candidate_pipeline(
            raw_export=raw_export,
            candidate=make_candidate(),
            account=self.account,
            open_positions=[],
        )
        self.assertEqual(result["status"], "BLOCKED_INVALID_OR_MISSING_INPUT")


if __name__ == "__main__":
    unittest.main()
