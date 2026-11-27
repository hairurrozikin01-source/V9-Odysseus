import math
import unittest

from mt5_strategy import analyze_snapshot, analyze_export


def make_snapshot(count=40, spread=0.02, rising=True):
    candles = []
    for index in range(count):
        base = 100 + (index * 0.08 if rising else -index * 0.08)
        close = base + math.sin(index * 1.7) * 0.25
        candles.append({
            "timestamp_utc": "2026-11-26T09:{:02d}:00Z".format(index % 60),
            "open": close - 0.03,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "tick_volume": 100,
        })
    return {
        "broker": "Exness",
        "account_type": "Raw Spread",
        "platform": "MT5",
        "mode": "READ ONLY",
        "orders_enabled": False,
        "symbol": "XAUUSD",
        "symbol_metadata": {"market_type": "METAL"},
        "tick": {"bid": 100.0, "ask": 100.0 + spread},
        "candles": candles,
    }


class MT5StrategyTests(unittest.TestCase):
    def test_rejects_non_read_only_snapshot(self):
        data = make_snapshot()
        data["mode"] = "LIVE"
        with self.assertRaises(ValueError):
            analyze_snapshot(data)

    def test_insufficient_candles_is_not_a_signal(self):
        result = analyze_snapshot(make_snapshot(count=10))
        self.assertEqual(result["status"], "INSUFFICIENT_DATA")
        self.assertFalse(result["orders_enabled"])

    def test_wide_spread_is_blocked(self):
        result = analyze_snapshot(make_snapshot(spread=10.0))
        self.assertEqual(result["status"], "BLOCKED_WIDE_SPREAD")
        self.assertFalse(result["automated_trade_instruction"])

    def test_result_never_enables_orders(self):
        result = analyze_snapshot(make_snapshot())
        self.assertEqual(result["mode"], "READ ONLY")
        self.assertFalse(result["orders_enabled"])
        self.assertFalse(result["automated_trade_instruction"])

    def test_export_requires_nonempty_snapshots(self):
        with self.assertRaises(ValueError):
            analyze_export({"mode": "READ ONLY", "snapshots": []})

    def test_export_returns_one_result_per_symbol(self):
        first = make_snapshot()
        second = make_snapshot()
        second["symbol"] = "EURUSD"
        second["symbol_metadata"] = {"market_type": "FOREX"}
        result = analyze_export({
            "mode": "READ ONLY",
            "snapshots": [first, second],
        })
        self.assertEqual(result["snapshot_count"], 2)
        self.assertEqual(len(result["results"]), 2)
        self.assertFalse(result["orders_enabled"])


if __name__ == "__main__":
    unittest.main()
