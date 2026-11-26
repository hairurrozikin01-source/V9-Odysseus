import unittest
from mt5_readonly_adapter import normalize_snapshot, normalize_export, normalize_tick, normalize_candles, SnapshotValidationError


def valid_snapshot():
    return {
        "broker": "Exness",
        "account_type": "Raw Spread",
        "platform": "MT5",
        "mode": "READ ONLY",
        "symbol": "XAUUSD",
        "symbol_metadata": {
            "symbol": "XAUUSD", "market_type": "METAL",
            "base_currency": "XAU", "quote_currency": "USD",
            "digits": 2, "point": 0.01, "tick_size": 0.01,
            "tick_value": 1.0, "contract_size": 100.0,
            "volume_min": 0.01, "volume_max": 200.0,
            "volume_step": 0.01, "trade_allowed": True
        },
        "tick": {
            "bid": 2300.10, "ask": 2300.20,
            "timestamp_utc": "2026-11-26T09:00:00Z"
        },
        "candles": [{
            "timestamp_utc": "2026-11-26T08:45:00Z",
            "open": 2299.0, "high": 2301.0, "low": 2298.0,
            "close": 2300.0, "tick_volume": 120
        }]
    }


class MT5ReadOnlyAdapterTests(unittest.TestCase):
    def test_valid_exness_raw_snapshot(self):
        result = normalize_snapshot(valid_snapshot())
        self.assertEqual(result["mode"], "READ ONLY")
        self.assertEqual(result["symbol"], "XAUUSD")
        self.assertFalse(result["orders_enabled"])
        self.assertFalse(result["wallet_access"])

    def test_rejects_non_read_only_mode(self):
        data = valid_snapshot()
        data["mode"] = "LIVE"
        with self.assertRaises(SnapshotValidationError):
            normalize_snapshot(data)

    def test_rejects_wrong_broker_or_account(self):
        data = valid_snapshot()
        data["broker"] = "Other"
        with self.assertRaises(SnapshotValidationError):
            normalize_snapshot(data)

    def test_rejects_crossed_market(self):
        with self.assertRaises(SnapshotValidationError):
            normalize_tick({"bid": 10, "ask": 9, "timestamp_utc": "2026-11-26T09:00:00Z"})

    def test_rejects_timezone_missing(self):
        with self.assertRaises(SnapshotValidationError):
            normalize_tick({"bid": 10, "ask": 11, "timestamp_utc": "2026-11-26T09:00:00"})

    def test_rejects_non_monotonic_candles(self):
        candle = {
            "timestamp_utc": "2026-11-26T08:45:00Z",
            "open": 10, "high": 12, "low": 9, "close": 11, "tick_volume": 2
        }
        with self.assertRaises(SnapshotValidationError):
            normalize_candles([candle, candle])

    def test_rejects_invalid_symbol_metadata(self):
        data = valid_snapshot()
        data["symbol_metadata"]["tick_value"] = 0
        with self.assertRaises(SnapshotValidationError):
            normalize_snapshot(data)


    def test_valid_multi_symbol_export(self):
        first = valid_snapshot()
        for key in ("broker", "account_type", "platform", "mode"):
            first.pop(key)
        export = {
            "broker": "Exness", "account_type": "Raw Spread",
            "platform": "MT5", "mode": "READ ONLY",
            "exported_at_utc": "2026-11-26T09:00:00Z",
            "snapshots": [first]
        }
        result = normalize_export(export)
        self.assertEqual(result["snapshot_count"], 1)
        self.assertFalse(result["orders_enabled"])

    def test_rejects_duplicate_symbols_in_export(self):
        first = valid_snapshot()
        for key in ("broker", "account_type", "platform", "mode"):
            first.pop(key)
        export = {
            "broker": "Exness", "account_type": "Raw Spread",
            "platform": "MT5", "mode": "READ ONLY",
            "exported_at_utc": "2026-11-26T09:00:00Z",
            "snapshots": [first, first]
        }
        with self.assertRaises(SnapshotValidationError):
            normalize_export(export)

    def test_rejects_stale_tick_in_export(self):
        first = valid_snapshot()
        for key in ("broker", "account_type", "platform", "mode"):
            first.pop(key)
        export = {
            "broker": "Exness", "account_type": "Raw Spread",
            "platform": "MT5", "mode": "READ ONLY",
            "exported_at_utc": "2026-11-26T09:03:00Z",
            "snapshots": [first]
        }
        with self.assertRaises(SnapshotValidationError):
            normalize_export(export)

    def test_rejects_tick_from_future(self):
        first = valid_snapshot()
        for key in ("broker", "account_type", "platform", "mode"):
            first.pop(key)
        export = {
            "broker": "Exness", "account_type": "Raw Spread",
            "platform": "MT5", "mode": "READ ONLY",
            "exported_at_utc": "2026-11-26T08:59:00Z",
            "snapshots": [first]
        }
        with self.assertRaises(SnapshotValidationError):
            normalize_export(export)

    def test_rejects_non_object_snapshot(self):
        export = {
            "broker": "Exness", "account_type": "Raw Spread",
            "platform": "MT5", "mode": "READ ONLY",
            "exported_at_utc": "2026-11-26T09:00:00Z",
            "snapshots": ["invalid"]
        }
        with self.assertRaises(SnapshotValidationError):
            normalize_export(export)

    def test_rejects_empty_export(self):
        export = {
            "broker": "Exness", "account_type": "Raw Spread",
            "platform": "MT5", "mode": "READ ONLY",
            "exported_at_utc": "2026-11-26T09:00:00Z",
            "snapshots": []
        }
        with self.assertRaises(SnapshotValidationError):
            normalize_export(export)

    def test_rejects_symbol_mismatch(self):
        data = valid_snapshot()
        data["symbol"] = "EURUSD"
        with self.assertRaises(SnapshotValidationError):
            normalize_snapshot(data)


if __name__ == "__main__":
    unittest.main()
