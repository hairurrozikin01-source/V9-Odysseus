import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class PersistentStateTests(unittest.TestCase):
    def test_save_json_creates_directory_and_round_trips(self):
        payload = [{"symbol": "BTCUSDT", "status": "PENDING"}]
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / ".v9-state" / "history.json"
            main.save_json(str(target), payload)
            with patch.object(main, "HISTORY_FILE", str(target)):
                self.assertEqual(main.load_history(), payload)
            self.assertFalse(Path(str(target) + ".tmp").exists())

    def test_corrupt_history_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "history.json"
            target.write_text("{broken", encoding="utf-8")
            with patch.object(main, "HISTORY_FILE", str(target)):
                with self.assertRaises(RuntimeError):
                    main.load_history()

    def test_performance_counts_positive_negative_neutral_and_pending(self):
        history = [
            {"validation": {
                "30m": {"status": "POSITIVE"},
                "1h": {"status": "NEGATIVE"},
            }},
            {"validation": {
                "30m": {"status": "NEUTRAL"},
                "1h": {"status": "PENDING"},
            }},
        ]
        stats = main.calculate_performance(history)
        self.assertEqual(stats["total_completed"], 3)
        self.assertEqual(stats["positive"], 1)
        self.assertEqual(stats["negative"], 1)
        self.assertEqual(stats["neutral"], 1)
        self.assertEqual(stats["pending"], 1)
        self.assertEqual(stats["success_rate_pct"], 50.0)


if __name__ == "__main__":
    unittest.main()
