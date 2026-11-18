import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from trading_desk.paper_controller import GuardedPaperController, PriceObservation
from trading_desk.paper_stops import process_stop_observation
from trading_desk.persistent_paper import PersistentPaperDesk


class PaperStopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.desk = PersistentPaperDesk(str(Path(self.temp.name) / "desk.sqlite"))
        self.controller = GuardedPaperController(self.desk, frozenset({"approved-v1"}))
        self.now = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
        obs = PriceObservation("BTC/USD", 100, self.now)
        self.assertTrue(self.controller.reserve(
            "entry", strategy_id="approved-v1", symbol="BTC/USD",
            price=100, stop_price=95, quantity=1, observation=obs, now=self.now))
        self.assertTrue(self.controller.fill("entry"))

    def test_stop_executes_at_gapped_price_not_stop_price(self):
        result = process_stop_observation(
            self.controller, PriceObservation("BTC/USD", 90, self.now), now=self.now)
        self.assertEqual(result.triggered, 1)
        self.assertEqual(result.realized_pnl_usd, -10)
        self.assertEqual(self.desk.snapshot().cash_usd, 490)
        self.assertEqual(len(self.desk.snapshot().positions), 0)

    def test_no_exit_above_stop(self):
        result = process_stop_observation(
            self.controller, PriceObservation("BTC/USD", 97, self.now), now=self.now)
        self.assertEqual(result.triggered, 0)
        self.assertEqual(len(self.desk.snapshot().positions), 1)

    def test_stale_observation_cannot_trigger_exit(self):
        from datetime import timedelta
        with self.assertRaises(ValueError):
            process_stop_observation(
                self.controller,
                PriceObservation("BTC/USD", 90, self.now - timedelta(minutes=2)),
                now=self.now)
        self.assertEqual(len(self.desk.snapshot().positions), 1)


if __name__ == "__main__":
    unittest.main()
