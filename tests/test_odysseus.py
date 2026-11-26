import unittest

import odysseus


class OdysseusAuditTests(unittest.TestCase):
    def setUp(self):
        self.report = {
            "version": "V9.4.6",
            "scan_time_utc": "2026-11-26 00:00:00 UTC",
            "mode": "READ ONLY",
            "universe_count": 3,
            "failed_count": 0,
            "results": [
                {
                    "symbol": "BTCUSDT",
                    "score": 90,
                    "rsi_15m": 62,
                    "volume_ratio_15m": 2.1,
                    "trend_30m_bullish": True,
                    "trend_1h_bullish": True,
                },
                {
                    "symbol": "HOTUSDT",
                    "score": 80,
                    "rsi_15m": 82,
                    "volume_ratio_15m": 1.1,
                    "trend_30m_bullish": True,
                    "trend_1h_bullish": False,
                },
            ],
            "failures": [],
        }

    def test_safe_signal_is_monitor_only(self):
        result = odysseus.audit_report(self.report)
        self.assertEqual(result["signals"][1]["symbol"], "BTCUSDT")
        self.assertEqual(result["signals"][1]["decision"], "MONITOR")
        self.assertFalse(result["safety"]["orders_enabled"])

    def test_overheated_and_weak_signal_requires_review(self):
        result = odysseus.audit_report(self.report)
        hot = next(x for x in result["signals"] if x["symbol"] == "HOTUSDT")
        self.assertEqual(hot["decision"], "REVIEW")
        self.assertIn("RSI_OVERBOUGHT", hot["risk_flags"])
        self.assertIn("VOLUME_CONFIRMATION_WEAK", hot["risk_flags"])
        self.assertIn("MULTI_TIMEFRAME_TREND_NOT_CONFIRMED", hot["risk_flags"])

    def test_unexpected_mode_is_critical(self):
        report = dict(self.report, mode="LIVE")
        result = odysseus.audit_report(report)
        self.assertEqual(result["system_flags"][0]["severity"], "CRITICAL")
        self.assertFalse(result["safety"]["automated_trade_instruction"])

    def test_empty_scan_is_not_forced_into_a_trade(self):
        report = dict(self.report, results=[])
        result = odysseus.audit_report(report)
        self.assertEqual(result["audited_signal_count"], 0)
        self.assertIn("Tidak ada sinyal V9", result["recommendations"][0])

    def test_invalid_report_rejected(self):
        with self.assertRaises(ValueError):
            odysseus.audit_report([])


if __name__ == "__main__":
    unittest.main()
