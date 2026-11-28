import unittest

from paper_trading_simulator import simulate


def signal(symbol, entry_time, entry=100.0, exit_price=102.0, status="POSITIVE"):
    return {
        "symbol": symbol,
        "direction": "BUY",
        "entry_price": entry,
        "entry_time_ms": entry_time,
        "validation": {
            "30m": {"status": "PENDING"},
            "1h": {"status": status, "exit_price": exit_price},
        },
    }


class PaperTradingSimulatorTests(unittest.TestCase):
    def test_starts_with_one_million_and_applies_costs(self):
        report = simulate([signal("BTCUSDT", 1_000_000)])
        summary = report["summary"]
        self.assertEqual(summary["initial_capital_idr"], 1_000_000)
        self.assertEqual(summary["completed_trades"], 1)
        self.assertEqual(summary["wins"], 1)
        self.assertAlmostEqual(summary["net_profit_idr"], 1_700, places=2)
        self.assertFalse(report["real_orders_enabled"])
        self.assertFalse(report["exchange_connection_enabled"])

    def test_only_one_position_at_a_time(self):
        report = simulate([
            signal("BTCUSDT", 1_000_000),
            signal("ETHUSDT", 1_030_000),
            signal("SOLUSDT", 1_060_000),
        ])
        self.assertEqual(report["summary"]["completed_trades"], 2)
        self.assertEqual(report["summary"]["skipped_overlapping_signals"], 1)

    def test_pending_signals_do_not_change_balance(self):
        report = simulate([signal("BTCUSDT", 1_000_000, status="PENDING")])
        self.assertEqual(report["summary"]["pending_signals"], 1)
        self.assertEqual(report["summary"]["ending_balance_idr"], 1_000_000)
        self.assertIsNone(report["summary"]["win_rate_pct"])

    def test_loss_includes_round_trip_costs(self):
        report = simulate([signal("BTCUSDT", 1_000_000, exit_price=99.0)])
        self.assertEqual(report["summary"]["losses"], 1)
        self.assertLess(report["summary"]["net_profit_idr"], -1_000)

    def test_rejects_invalid_configuration(self):
        with self.assertRaises(ValueError):
            simulate([], initial_capital=0)
        with self.assertRaises(ValueError):
            simulate([], allocation_pct=0)


if __name__ == "__main__":
    unittest.main()
