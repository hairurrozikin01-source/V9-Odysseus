import unittest

import odysseus


class OdysseusAuditTests(unittest.TestCase):
    def setUp(self):
        self.report = {
            "version": "V9.4.6",
            "scan_time_utc": "2026-11-26 00:00:00 UTC",
            "mode": "READ ONLY",
            "universe_count": 2,
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
        btc = next(x for x in result["signals"] if x["symbol"] == "BTCUSDT")
        self.assertEqual(btc["decision"], "MONITOR")
        self.assertEqual(result["audit_status"], "CLEAR")
        self.assertFalse(result["safety"]["orders_enabled"])

    def test_overheated_signal_requires_review(self):
        result = odysseus.audit_report(self.report)
        hot = next(x for x in result["signals"] if x["symbol"] == "HOTUSDT")
        self.assertEqual(hot["decision"], "REVIEW")
        self.assertIn("RSI_OVERBOUGHT", hot["risk_flags"])
        self.assertIn("VOLUME_CONFIRMATION_WEAK", hot["risk_flags"])
        self.assertIn("MULTI_TIMEFRAME_TREND_NOT_CONFIRMED", hot["risk_flags"])

    def test_unexpected_mode_blocks_audit(self):
        result = odysseus.audit_report(dict(self.report, mode="LIVE"))
        self.assertEqual(result["audit_status"], "BLOCKED")
        self.assertEqual(result["system_flags"][0]["severity"], "CRITICAL")

    def test_invalid_numeric_data_blocks_audit(self):
        rows = [dict(self.report["results"][0], rsi_15m=150)]
        result = odysseus.audit_report(dict(self.report, results=rows, universe_count=1))
        self.assertEqual(result["audit_status"], "BLOCKED")
        self.assertIn("RSI_INVALID", result["signals"][0]["risk_flags"])

    def test_missing_trend_confirmation_blocks_audit(self):
        row = dict(self.report["results"][0], trend_1h_bullish=None)
        result = odysseus.audit_report(dict(self.report, results=[row], universe_count=1))
        self.assertEqual(result["audit_status"], "BLOCKED")

    def test_failure_count_mismatch_causes_caution(self):
        result = odysseus.audit_report(dict(self.report, failed_count=2))
        self.assertEqual(result["audit_status"], "CAUTION")
        self.assertIn("FAILURE_COUNT_MISMATCH", [x["code"] for x in result["system_flags"]])

    def test_empty_scan_is_not_forced_into_trade(self):
        result = odysseus.audit_report(dict(self.report, results=[], universe_count=0))
        self.assertEqual(result["audited_signal_count"], 0)
        self.assertEqual(result["audit_status"], "CLEAR")
        self.assertFalse(result["safety"]["automated_trade_instruction"])

    def test_invalid_report_rejected(self):
        with self.assertRaises(ValueError):
            odysseus.audit_report([])


if __name__ == "__main__":
    unittest.main()
