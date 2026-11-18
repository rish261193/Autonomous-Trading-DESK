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

    def test_reserve_with_valid_observation_then_stop_via_controller(self):
        obs = PriceObservation("BTC/USD", 100, self.now)
        self.assertTrue(self.controller.reserve(
            "entry", strategy_id="approved", symbol="BTC/USD", price=100,
            stop_price=95, quantity=1, observation=obs, now=self.now))
        self.assertTrue(self.controller.fill(
            "entry", strategy_id="approved", observation=obs, now=self.now))
        self.assertTrue(self.controller.observe(
            PriceObservation("BTC/USD", 90, self.now), now=self.now))
        self.assertEqual(len(self.desk.snapshot().positions), 0)
        self.assertEqual(self.desk.snapshot().cash_usd, 490)

    def test_direct_ledger_mark_cannot_bypass_stop(self):
        obs = PriceObservation("BTC/USD", 100, self.now)
        self.assertTrue(self.controller.reserve(
            "entry", strategy_id="approved", symbol="BTC/USD", price=100,
            stop_price=95, quantity=1, observation=obs, now=self.now))
        self.assertTrue(self.controller.fill(
            "entry", strategy_id="approved", observation=obs, now=self.now))
        self.desk.mark("BTC/USD", 90)
        self.assertEqual(len(self.desk.snapshot().positions), 0)

    def test_valid_observation_accepted(self):
        obs = PriceObservation("BTC/USD", 100, self.now)
        self.assertTrue(self.controller.valid_observation(obs, now=self.now))


if __name__ == "__main__":
    unittest.main()
