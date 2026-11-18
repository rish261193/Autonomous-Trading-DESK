import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_desk.paper_controller import GuardedPaperController, PriceObservation
from trading_desk.persistent_paper import PersistentPaperDesk


class PaperControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
        # Audit change: deterministic trusted clock injected at construction.
        self.desk = PersistentPaperDesk(str(Path(self.temp.name) / "desk.sqlite"),
                                        clock=lambda: self.now)
        self.control = GuardedPaperController(self.desk, frozenset({"approved-v1"}))
        self.observation = PriceObservation("BTC/USD", 100, self.now)
        self.order = dict(strategy_id="approved-v1", symbol="BTC/USD",
                          price=100, stop_price=95, quantity=1,
                          observation=self.observation, now=self.now)

    def test_approved_and_fresh_reservation(self):
        self.assertTrue(self.control.reserve("order-1", **self.order))

    def test_unapproved_strategy_fails_closed(self):
        self.assertFalse(self.control.reserve(
            "order-1", **(self.order | {"strategy_id": "unknown-v1"})))

    def test_stale_and_future_prices_rejected(self):
        for offset in (-61, 1):
            with self.subTest(offset=offset):
                obs = PriceObservation("BTC/USD", 100,
                                       self.now + timedelta(seconds=offset))
                self.assertFalse(self.control.reserve(
                    "order-1", **(self.order | {"observation": obs})))

    def test_fill_requires_current_mark_and_matching_strategy(self):
        self.assertTrue(self.control.reserve("order-1", **self.order))
        self.assertFalse(self.control.fill(
            "order-1", strategy_id="unknown-v1",
            observation=self.observation, now=self.now))
        self.desk.mark("BTC/USD", 101)
        self.assertFalse(self.control.fill(
            "order-1", strategy_id="approved-v1",
            observation=self.observation, now=self.now))
        self.assertEqual(self.desk.snapshot().cash_usd, 500)
        self.desk.mark("BTC/USD", 100)
        self.assertTrue(self.control.fill(
            "order-1", strategy_id="approved-v1",
            observation=self.observation, now=self.now))

    def test_direct_persistent_entry_disabled(self):
        with self.assertRaises(RuntimeError):
            self.desk.enter(strategy_id="approved-v1", symbol="BTC/USD",
                            price=100, stop_price=95, quantity=1,
                            strategy_authorized=True, market_data_fresh=True)


if __name__ == "__main__":
    unittest.main()
