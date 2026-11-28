import json
import unittest

import scripts.publish_readonly_reports as publisher


class ReadOnlyPublisherTests(unittest.TestCase):
    def setUp(self):
        self.v9 = {
            "version": "V9-test",
            "mode": "READ ONLY",
            "results": [],
        }
        self.risk = {
            "version": "risk-test",
            "mode": "READ ONLY",
            "risk_level": "OBSERVE",
            "flags": [],
            "metrics": {},
        }

    def test_build_payload_preserves_both_read_only_reports(self):
        payload = publisher.build_payload(self.v9, self.risk)
        decoded = json.loads(payload.decode("utf-8"))
        self.assertEqual(decoded["v9_report"]["mode"], "READ ONLY")
        self.assertEqual(decoded["risk_report"]["mode"], "READ ONLY")

    def test_rejects_non_read_only_v9_report(self):
        with self.assertRaises(RuntimeError):
            publisher.build_payload(dict(self.v9, mode="LIVE"), self.risk)

    def test_rejects_non_read_only_risk_report(self):
        with self.assertRaises(RuntimeError):
            publisher.build_payload(self.v9, dict(self.risk, mode="UNKNOWN"))

    def test_rejects_non_object_reports(self):
        with self.assertRaises(ValueError):
            publisher.build_payload([], self.risk)

    def test_rejects_missing_mode(self):
        report = dict(self.v9)
        del report["mode"]
        with self.assertRaises(RuntimeError):
            publisher.build_payload(report, self.risk)


if __name__ == "__main__":
    unittest.main()
