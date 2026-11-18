"""Adversarial Phase 2 checks; these are not a security certification."""
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from trading_desk.pending_orders import PendingOrders
from trading_desk.persistent_paper import PersistentPaperDesk


class AdversarialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "ledger.sqlite")
        self.desk = PersistentPaperDesk(self.path)
        self.desk.mark("BTC/USD", 100)
        self.orders = PendingOrders(self.desk)
        self.order = dict(strategy_id="approved-v1", symbol="BTC/USD",
                          price=100, stop_price=95, quantity=1,
                          strategy_authorized=True, market_data_fresh=True)

    def test_reject_forged_authorization_types(self):
        for field in ("strategy_authorized", "market_data_fresh"):
            for value in (1, "true", None, False):
                with self.subTest(field=field, value=value):
                    self.assertFalse(self.orders.reserve("invalid", **(self.order | {field: value})))
        self.assertEqual(self.desk.snapshot().cash_usd, 500)

    def test_parallel_reservations_never_exceed_risk(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(lambda i: self.orders.reserve(str(i), **self.order), range(16)))
        self.assertEqual(sum(outcomes), 1)
        self.assertEqual(self.desk.snapshot().cash_usd, 500)

    def test_tampered_pending_cash_fails_closed_on_restart(self):
        self.assertTrue(self.orders.reserve("a", **self.order))
        with sqlite3.connect(self.path) as db:
            payload = json.loads(db.execute("SELECT payload FROM reservations WHERE order_id='a'").fetchone()[0])
            payload["quantity"] = 6
            payload["notional"] = 600
            payload["risk"] = 30
            db.execute("UPDATE reservations SET payload=? WHERE order_id='a'", (json.dumps(payload),))
        with self.assertRaises(ValueError):
            PersistentPaperDesk(self.path)

    def test_kill_switch_survives_restart_and_blocks_fill(self):
        self.assertTrue(self.orders.reserve("a", **self.order))
        self.desk.halt()
        restarted = PersistentPaperDesk(self.path)
        self.assertFalse(PendingOrders(restarted).fill(
            "a", strategy_authorized=True, market_data_fresh=True,
            expected_strategy_id="approved-v1", expected_symbol="BTC/USD"))
        self.assertEqual(restarted.snapshot().cash_usd, 500)


if __name__ == "__main__":
    unittest.main()
