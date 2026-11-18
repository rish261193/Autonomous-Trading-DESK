"""Regression coverage for fail-closed UTC daily risk clock validation."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from trading_desk.persistent_paper import PersistentPaperDesk


class UtcClockSafetyTests(unittest.TestCase):
    def test_naive_datetime_is_rejected_without_mutating_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            desk = PersistentPaperDesk(str(Path(directory) / "paper.sqlite"))
            with self.assertRaises(ValueError):
                desk.roll_utc_day(now=datetime(2026, 11, 18, 12))
            self.assertFalse(desk.roll_utc_day(now=datetime.now(timezone.utc)))

    def test_aware_datetime_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            desk = PersistentPaperDesk(str(Path(directory) / "paper.sqlite"))
            self.assertFalse(desk.roll_utc_day(now=datetime.now(timezone.utc)))


if __name__ == "__main__":
    unittest.main()
