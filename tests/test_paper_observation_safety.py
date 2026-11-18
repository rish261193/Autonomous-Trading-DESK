"""Regression tests for fail-closed paper observation validation."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from trading_desk.paper_controller import GuardedPaperController, PriceObservation


class ObservationSafetyTests(unittest.TestCase):
    def setUp(self):
        # No persistent desk needed: invalid inputs must be rejected before side effects.
        with patch("trading_desk.paper_controller.PendingOrders"):
            self.controller = GuardedPaperController(MagicMock(), frozenset({"approved"}))
        self.now = datetime(2026, 11, 18, 20, 0, tzinfo=timezone.utc)

    def test_none_observation_rejected(self):
        self.assertFalse(self.controller.valid_observation(None, now=self.now))
        self.assertFalse(self.controller.reserve(
            "o1", strategy_id="approved", symbol="BTC/USD",
            price=100.0, stop_price=99.0, quantity=0.01,
            observation=None, now=self.now))

    def test_wrong_observation_type_rejected(self):
        self.assertFalse(self.controller.valid_observation({}, now=self.now))

    def test_naive_clock_rejected(self):
        observation = PriceObservation("BTC/USD", 100.0, self.now)
        self.assertFalse(self.controller.valid_observation(
            observation, now=datetime(2026, 11, 18, 20, 0)))

    def test_naive_observation_timestamp_rejected(self):
        observation = PriceObservation("BTC/USD", 100.0, datetime(2026, 11, 18, 20, 0))
        self.assertFalse(self.controller.valid_observation(observation, now=self.now))

    def test_fresh_valid_observation_accepted(self):
        observation = PriceObservation("BTC/USD", 100.0, self.now)
        self.assertTrue(self.controller.valid_observation(observation, now=self.now))


    def test_accepted_observation_processes_stops_atomically(self):
        observation = PriceObservation("BTC/USD", 100.0, self.now)
        with patch.object(self.controller.desk, "apply_stop_mark") as apply:
            self.assertTrue(self.controller.observe(observation, now=self.now))
            apply.assert_called_once_with("BTC/USD", 100.0)

    def test_invalid_observation_does_not_process_stops(self):
        with patch.object(self.controller.desk, "apply_stop_mark") as apply:
            self.assertFalse(self.controller.observe(None, now=self.now))
            apply.assert_not_called()

if __name__ == "__main__":
    unittest.main()
