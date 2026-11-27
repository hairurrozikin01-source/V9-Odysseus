import json
import os
import tempfile
import unittest

from mt5_quality_report import run


class MT5QualityReportRunnerTests(unittest.TestCase):
    def test_missing_export_creates_explicit_read_only_status(self):
        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, "report.json")
            report = run(os.path.join(directory, "missing.json"), output)
            with open(output, "r", encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertEqual(report["status"], "DATA_NOT_AVAILABLE")
            self.assertEqual(saved["status"], "DATA_NOT_AVAILABLE")
            self.assertFalse(saved["orders_enabled"])
            self.assertFalse(saved["new_risk_allowed"])

    def test_invalid_export_fails_closed_and_writes_report(self):
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "input.json")
            output = os.path.join(directory, "report.json")
            with open(source, "w", encoding="utf-8") as handle:
                json.dump({"mode": "LIVE"}, handle)
            report = run(source, output)
            self.assertEqual(report["status"], "BLOCKED_INVALID_EXPORT")
            self.assertFalse(report["automated_trade_instruction"])


if __name__ == "__main__":
    unittest.main()
