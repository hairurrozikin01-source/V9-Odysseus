import unittest

import risk_monitor


class RiskMonitorTests(unittest.TestCase):
    def setUp(self):
        self.v9 = {
            "version": "V9.4.6",
            "mode": "READ ONLY",
            "failed_count": 0,
            "results": [{"symbol": "BTCUSDT"}],
            "failures": [],
        }
        self.shib = {
            "version": "SHIB-HUNTER-0.1.0",
            "mode": "READ ONLY",
            "failure_count": 0,
            "candidates": [],
            "failures": [],
        }

    def test_clean_reports_are_observe_only(self):
        result = risk_monitor.evaluate_risk(self.v9, self.shib)
        self.assertEqual(result["risk_level"], "OBSERVE")
        self.assertFalse(result["safety"]["orders_enabled"])

    def test_unexpected_mode_blocks_report(self):
        result = risk_monitor.evaluate_risk(
            dict(self.v9, mode="LIVE"), self.shib
        )
        self.assertEqual(result["risk_level"], "BLOCKED")
        self.assertIn("V9_MODE_NOT_READ_ONLY", [x["code"] for x in result["flags"]])

    def test_failure_count_mismatch_blocks_report(self):
        result = risk_monitor.evaluate_risk(
            dict(self.v9, failed_count=2), self.shib
        )
        self.assertEqual(result["risk_level"], "BLOCKED")

    def test_scan_failures_cause_caution(self):
        v9 = dict(self.v9, failed_count=1, failures=[{"symbol": "ETHUSDT"}])
        result = risk_monitor.evaluate_risk(v9, self.shib)
        self.assertEqual(result["risk_level"], "CAUTION")
        self.assertIn("V9_ANALYSIS_FAILURES", [x["code"] for x in result["flags"]])

    def test_unverified_watchlist_token_causes_caution(self):
        candidate = {"decision": "WATCHLIST", "security_status": "NOT_VERIFIED"}
        shib = dict(self.shib, candidates=[candidate])
        result = risk_monitor.evaluate_risk(self.v9, shib)
        self.assertEqual(result["risk_level"], "CAUTION")
        self.assertEqual(result["metrics"]["watchlist_security_unverified_count"], 1)

    def test_empty_reports_do_not_create_buy_instruction(self):
        result = risk_monitor.evaluate_risk(
            dict(self.v9, results=[]), self.shib
        )
        self.assertEqual(result["risk_level"], "OBSERVE")
        self.assertFalse(result["safety"]["automated_trade_instruction"])

    def test_invalid_input_rejected(self):
        with self.assertRaises(ValueError):
            risk_monitor.evaluate_risk([], self.shib)


if __name__ == "__main__":
    unittest.main()
