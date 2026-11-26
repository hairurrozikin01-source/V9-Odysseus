import unittest

from dashboard import build_dashboard


class DashboardTests(unittest.TestCase):
    def test_builds_mobile_read_only_dashboard(self):
        page = build_dashboard({
            "v9": {"mode": "READ ONLY", "results": [
                {"symbol": "BTCUSDT", "score": 82, "rsi_15m": 55, "status": "MONITOR"}
            ]},
            "shib": {"candidates": [
                {"symbol": "TEST", "chain_id": "solana", "score": 70,
                 "decision": "WATCHLIST", "security_status": "UNVERIFIED"}
            ]},
            "odysseus": {"audited_signals": [{"symbol": "BTCUSDT"}]},
            "risk": {"risk_level": "CAUTION", "summary": "Perlu pemeriksaan.",
                     "flags": [{"severity": "WARNING", "message": "Data belum lengkap."}]},
        }, generated_at="2026-11-26 00:00 UTC")
        self.assertIn("V9", page)
        self.assertIn("BTCUSDT", page)
        self.assertIn("READ ONLY", page)
        self.assertIn("Data belum lengkap", page)
        self.assertIn("viewport", page)
        self.assertIn("UNVERIFIED", page)

    def test_missing_reports_are_explicit(self):
        page = build_dashboard({}, generated_at="fixed")
        self.assertIn("Laporan belum tersedia", page)
        self.assertIn("Belum ada data sinyal V9", page)
        self.assertIn("Belum ada kandidat watchlist", page)

    def test_escapes_untrusted_report_text(self):
        page = build_dashboard({
            "v9": {"results": [{"symbol": "<script>alert(1)</script>",
                                "score": 1, "rsi_15m": 1, "status": "x"}]}
        })
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)


if __name__ == "__main__":
    unittest.main()
