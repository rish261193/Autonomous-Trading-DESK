"""Regression tests for fail-closed paper observation validation."""
import unittest
from datetime import datetime, timezone
from trading_desk.paper_controller import GuardedPaperController, PriceObservation


class ObservationSafetyTests(unittest.TestCase):
    def setUp(self):
        # No persistent desk needed: invalid inputs must be rejected before side effects.
        self.controller = GuardedPaperController(None, frozenset({"approved"}))
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


if __name__ == "__main__":
    unittest.main()
