import unittest

from mt5_data_quality import assess_snapshot_quality, assess_export_quality\nfrom mt5_quality_runner import build_quality_report


def make_snapshot():
    candles = []
    for i in range(40):
        close = 2300.0 + (i * 0.01)
        candles.append({
            "timestamp_utc": "2026-11-26T08:{:02d}:00Z".format(i % 60),
            "open": close - 0.02, "high": close + 0.10,
            "low": close - 0.10, "close": close, "tick_volume": 100
        })
    return {
        "broker": "Exness", "platform": "MT5", "account_type": "Raw Spread",
        "mode": "READ ONLY", "orders_enabled": False, "symbol": "XAUUSD",
        "symbol_metadata": {"point": 0.01, "digits": 2, "trade_allowed": True},
        "tick": {"bid": 2300.38, "ask": 2300.39,
                 "timestamp_utc": "2026-11-26T09:00:00Z"},
        "candles": candles,
    }


class MT5DataQualityTests(unittest.TestCase):
    def test_valid_snapshot_passes_and_never_enables_orders(self):
        result = assess_snapshot_quality(make_snapshot(), "2026-11-26T09:00:10Z")
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["orders_enabled"])
        self.assertFalse(result["new_risk_allowed"])

    def test_stale_tick_is_rejected(self):
        data = make_snapshot()
        data["tick"]["timestamp_utc"] = "2026-11-26T08:50:00Z"
        with self.assertRaises(ValueError):
            assess_snapshot_quality(data, "2026-11-26T09:00:10Z")

    def test_nontradable_symbol_is_blocked(self):
        data = make_snapshot()
        data["symbol_metadata"]["trade_allowed"] = False
        result = assess_snapshot_quality(data, "2026-11-26T09:00:10Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("SYMBOL_NOT_TRADE_ALLOWED",
                      [item["code"] for item in result["findings"]])

    def test_bad_price_precision_is_blocked(self):
        data = make_snapshot()
        data["tick"]["bid"] = 2300.381
        result = assess_snapshot_quality(data, "2026-11-26T09:00:10Z")
        self.assertEqual(result["status"], "BLOCKED")

    def test_wide_spread_is_blocked(self):
        data = make_snapshot()
        data["tick"]["ask"] = 2301.50
        result = assess_snapshot_quality(data, "2026-11-26T09:00:10Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("SPREAD_TOO_WIDE",
                      [item["code"] for item in result["findings"]])

    def test_export_reports_each_symbol(self):
        first = make_snapshot()
        second = make_snapshot()
        second["symbol"] = "EURUSD"
        export = {"mode": "READ ONLY", "exported_at_utc": "2026-11-26T09:00:10Z",
                  "snapshots": [first, second]}
        result = assess_export_quality(export)
        self.assertEqual(result["snapshot_count"], 2)
        self.assertFalse(result["automated_trade_instruction"])

    def test_runner_normalizes_raw_export_before_quality_assessment(self):
        snapshot = make_snapshot()
        snapshot["symbol_metadata"].update({
            "symbol": "XAUUSD", "market_type": "METAL",
            "base_currency": "XAU", "quote_currency": "USD",
            "tick_size": 0.01, "tick_value": 1.0,
            "tick_value_currency": "USD", "contract_size": 100.0,
            "volume_min": 0.01, "volume_max": 200.0, "volume_step": 0.01
        })
        raw = {
            "broker": "Exness", "platform": "MT5", "account_type": "Raw Spread",
            "account_currency": "USD", "mode": "READ ONLY",
            "exported_at_utc": "2026-11-26T09:00:10Z", "snapshots": [snapshot]
        }
        report = build_quality_report(raw)
        self.assertEqual(report["snapshot_count"], 1)
        self.assertFalse(report["orders_enabled"])
        self.assertFalse(report["automated_trade_instruction"])

    def test_invalid_export_rejected(self):
        with self.assertRaises(ValueError):
            assess_export_quality({"mode": "LIVE", "snapshots": []})


if __name__ == "__main__":
    unittest.main()
