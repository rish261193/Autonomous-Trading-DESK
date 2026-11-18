import tempfile
import unittest
from pathlib import Path

from trading_desk.pending_orders import PendingOrders
from trading_desk.persistent_paper import PersistentPaperDesk


class PendingOrderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "paper.sqlite")
        self.desk = PersistentPaperDesk(self.path)
        self.desk.mark("BTC/USD", 100)
        self.orders = PendingOrders(self.desk)
        self.intent = dict(strategy_id="momentum-v1", symbol="BTC/USD",
                           price=100, stop_price=95, quantity=1,
                           strategy_authorized=True, market_data_fresh=True)

    def test_duplicate_order_id_never_reused(self):
        self.assertTrue(self.orders.reserve("a", **self.intent))
        self.assertFalse(self.orders.reserve("a", **self.intent))
        self.assertTrue(self.orders.cancel("a"))
        self.assertFalse(self.orders.reserve("a", **self.intent))

    def test_pending_risk_reservation_blocks_second_order(self):
        self.assertTrue(self.orders.reserve("a", **self.intent))
        self.assertFalse(self.orders.reserve("b", **self.intent))
        self.assertEqual(self.desk.snapshot().cash_usd, 500)

    def test_fill_is_atomic_and_idempotent(self):
        self.assertTrue(self.orders.reserve("a", **self.intent))
        self.assertTrue(self.orders.fill("a"))
        self.assertFalse(self.orders.fill("a"))
        state = PersistentPaperDesk(self.path).snapshot()
        self.assertEqual(state.cash_usd, 400)
        self.assertEqual(len(state.positions), 1)

    def test_cancel_releases_reserved_risk(self):
        self.assertTrue(self.orders.reserve("a", **self.intent))
        self.assertTrue(self.orders.cancel("a"))
        self.assertFalse(self.orders.fill("a"))
        self.assertTrue(self.orders.reserve("b", **self.intent))

    def test_kill_switch_blocks_pending_fill(self):
        self.assertTrue(self.orders.reserve("a", **self.intent))
        self.desk.halt()
        self.assertFalse(self.orders.fill("a"))
        self.assertEqual(self.desk.snapshot().cash_usd, 500)

    def test_reservations_survive_restart(self):
        self.assertTrue(self.orders.reserve("a", **self.intent))
        restarted = PendingOrders(PersistentPaperDesk(self.path))
        self.assertFalse(restarted.reserve("a", **self.intent))
        self.assertFalse(restarted.reserve("b", **self.intent))


if __name__ == "__main__":
    unittest.main()
