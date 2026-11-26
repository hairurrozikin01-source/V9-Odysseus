import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from transaction_audit import AuditJournal, AuditJournalError


class AuditJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "audit" / "events.jsonl"
        self.journal = AuditJournal(self.path)
        self.now = datetime(2026, 11, 26, 13, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp.cleanup()

    def test_empty_journal_is_valid(self):
        self.assertEqual(self.journal.verify()["count"], 0)

    def test_append_creates_verifiable_hash_chain(self):
        first = self.journal.append(
            {"proposal_id": "p-1", "action": "APPROVE"},
            recorded_at=self.now,
        )
        second = self.journal.append(
            {"proposal_id": "p-2", "action": "REJECT"},
            recorded_at=self.now,
        )
        result = self.journal.verify()
        self.assertEqual(result["count"], 2)
        self.assertEqual(second["previous_hash"], first["event_hash"])
        self.assertTrue(result["valid"])

    def test_tampering_is_detected(self):
        self.journal.append({"proposal_id": "p-1", "action": "APPROVE"}, recorded_at=self.now)
        item = json.loads(self.path.read_text(encoding="utf-8"))
        item["event"]["action"] = "REJECT"
        self.path.write_text(json.dumps(item) + "\n", encoding="utf-8")
        with self.assertRaises(AuditJournalError):
            self.journal.verify()

    def test_secret_fields_are_rejected(self):
        with self.assertRaises(AuditJournalError):
            self.journal.append({"proposal_id": "p-1", "password": "do-not-store"})

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaises(AuditJournalError):
            self.journal.append(
                {"proposal_id": "p-1", "action": "APPROVE"},
                recorded_at=datetime(2026, 11, 26, 13, 0),
            )

    def test_corrupt_journal_cannot_be_appended(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("{broken json}\n", encoding="utf-8")
        with self.assertRaises(AuditJournalError):
            self.journal.append({"proposal_id": "p-2", "action": "APPROVE"})


if __name__ == "__main__":
    unittest.main()
