"""Validate caller inputs without bypassing the audited trusted clock."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from trading_desk.paper_controller import GuardedPaperController, PriceObservation
from trading_desk.persistent_paper import PersistentPaperDesk


class AuditObservationGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = datetime(2026, 11, 18, 16, tzinfo=timezone.utc)
        self.desk = PersistentPaperDesk(
            str(Path(self.temp.name) / "desk.sqlite"), clock=lambda: self.now)
        self.controller = GuardedPaperController(self.desk, frozenset({"approved"}))

    def test_none_observation_rejected(self):
        self.assertFalse(self.controller.valid_observation(None, now=self.now))
        self.assertFalse(self.controller.reserve(
            "none", strategy_id="approved", symbol="BTC/USD", price=100,
            stop_price=95, quantity=1, observation=None, now=self.now))

    def test_wrong_type_rejected(self):
        self.assertFalse(self.controller.valid_observation({}, now=self.now))
        self.assertFalse(self.controller.reserve(
            "wrong", strategy_id="approved", symbol="BTC/USD", price=100,
            stop_price=95, quantity=1, observation={}, now=self.now))

    def test_naive_observation_timestamp_rejected(self):
        obs = PriceObservation("BTC/USD", 100, datetime(2026, 11, 18, 16))
        self.assertFalse(self.controller.valid_observation(obs, now=self.now))

    def test_valid_observation_accepted(self):
        obs = PriceObservation("BTC/USD", 100, self.now)
        self.assertTrue(self.controller.valid_observation(obs, now=self.now))


if __name__ == "__main__":
    unittest.main()
