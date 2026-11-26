import unittest

import shib_hunter


class ShibHunterTests(unittest.TestCase):
    def setUp(self):
        self.metrics = {
            "name": "Test Token",
            "symbol": "TEST",
            "price_usd": 0.001,
            "liquidity_usd": 150_000,
            "volume_1h_usd": 5_000,
            "volume_24h_usd": 300_000,
            "buys_24h": 700,
            "sells_24h": 300,
            "transactions_24h": 1000,
            "price_change_1h_pct": 12,
            "price_change_24h_pct": 35,
            "fdv_usd": 2_000_000,
            "market_cap_usd": 1_500_000,
            "pool_age_hours": 10,
            "pair_address": "pair",
            "dex_id": "test-dex",
            "pair_url": "https://example.invalid/pair",
        }

    def test_balanced_candidate_passes(self):
        score, rejected = shib_hunter.score_candidate(self.metrics)
        self.assertGreaterEqual(score, 55)
        self.assertEqual(rejected, [])

    def test_thin_liquidity_is_rejected(self):
        metrics = dict(self.metrics, liquidity_usd=1_000)
        score, rejected = shib_hunter.score_candidate(metrics)
        self.assertEqual(score, 0)
        self.assertIn("liquidity_below_balanced_floor", rejected)

    def test_extreme_price_spike_is_rejected(self):
        metrics = dict(self.metrics, price_change_1h_pct=180)
        score, rejected = shib_hunter.score_candidate(metrics)
        self.assertEqual(score, 0)
        self.assertIn("overheated_pump_protection", rejected)

    def test_heavy_sell_pressure_is_rejected(self):
        metrics = dict(self.metrics, buys_24h=100, sells_24h=500)
        score, rejected = shib_hunter.score_candidate(metrics)
        self.assertEqual(score, 0)
        self.assertIn("sell_pressure_high", rejected)


if __name__ == "__main__":
    unittest.main()
