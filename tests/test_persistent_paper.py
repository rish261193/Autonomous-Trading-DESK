import json
from datetime import datetime, timedelta, timezone
import sqlite3
import tempfile
import unittest
from pathlib import Path

from trading_desk.persistent_paper import PersistentPaperDesk
from trading_desk.pending_orders import PendingOrders


class PersistentPaperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "paper.sqlite")
        self.desk = PersistentPaperDesk(self.path)
        self.order = dict(strategy_id="momentum-v1", symbol="BTC/USD",
                          price=100, stop_price=95, quantity=1,
                          strategy_authorized=True, market_data_fresh=True)
        self.desk.mark("BTC/USD", 100)
        self.orders = PendingOrders(self.desk)

    def test_restart_recovers_cash_positions_and_marks(self):
        self.assertTrue(self.orders.reserve("entry", **self.order))
        self.assertTrue(self.orders.fill("entry", strategy_authorized=True, market_data_fresh=True, expected_strategy_id="momentum-v1", expected_symbol="BTC/USD"))
        restarted = PersistentPaperDesk(self.path)
        state = restarted.snapshot()
        self.assertEqual(state.cash_usd, 400)
        self.assertEqual(len(state.positions), 1)
        self.assertEqual(state.marks["BTC/USD"], 100)
        self.assertFalse(PendingOrders(restarted).reserve("entry", **self.order))

    def test_kill_switch_persists_across_restart(self):
        self.desk.halt()
        restarted = PersistentPaperDesk(self.path)
        self.assertTrue(restarted.snapshot().kill_switch)
        self.assertFalse(PendingOrders(restarted).reserve("blocked", **self.order))

    def test_rejected_order_does_not_mutate_balances(self):
        self.assertFalse(self.orders.reserve("entry", **(self.order | {"quantity": 2})))
        self.assertEqual(PersistentPaperDesk(self.path).snapshot().cash_usd, 500)

    def test_close_persists_realized_pnl(self):
        self.assertTrue(self.orders.reserve("entry", **self.order))
        self.assertTrue(self.orders.fill("entry", strategy_authorized=True, market_data_fresh=True, expected_strategy_id="momentum-v1", expected_symbol="BTC/USD"))
        self.desk.mark("BTC/USD", 102)
        self.assertEqual(self.desk.close(0, 102), 2)
        state = PersistentPaperDesk(self.path).snapshot()
        self.assertEqual(state.cash_usd, 502)
        self.assertEqual(state.daily_realized_pnl_usd, 2)
        self.assertEqual(len(state.positions), 0)

    def test_daily_reset_preserves_positions(self):
        self.assertTrue(self.orders.reserve("entry", **self.order))
        self.assertTrue(self.orders.fill("entry", strategy_authorized=True, market_data_fresh=True, expected_strategy_id="momentum-v1", expected_symbol="BTC/USD"))
        self.desk.mark("BTC/USD", 102)
        with self.assertRaises(RuntimeError):
            self.desk.reset_daily_baseline()
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        self.assertTrue(self.desk.roll_utc_day(now=tomorrow))
        self.assertFalse(self.desk.roll_utc_day(now=tomorrow))
        state = PersistentPaperDesk(self.path).snapshot()
        self.assertEqual(state.day_start_equity_usd, 502)
        self.assertEqual(len(state.positions), 1)

    def test_utc_roll_survives_restart_and_rejects_rollback(self):
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        self.assertTrue(self.desk.roll_utc_day(now=tomorrow))
        restarted = PersistentPaperDesk(self.path)
        self.assertFalse(restarted.roll_utc_day(now=tomorrow))
        with self.assertRaises(ValueError):
            restarted.roll_utc_day(now=tomorrow - timedelta(days=1))

    def test_reconciliation_rejects_tampered_position_risk(self):
        self.assertTrue(self.orders.reserve("entry", **self.order))
        self.assertTrue(self.orders.fill("entry", strategy_authorized=True,
                                         market_data_fresh=True,
                                         expected_strategy_id="momentum-v1",
                                         expected_symbol="BTC/USD"))
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT payload FROM state WHERE id=1").fetchone()
            payload = json.loads(row[0])
            payload["positions"][0]["risk_usd"] = 0.01
            db.execute("UPDATE state SET payload=? WHERE id=1",
                       (json.dumps(payload),))
        with self.assertRaises(ValueError):
            PersistentPaperDesk(self.path)

    def test_corrupt_reservation_fails_restart_reconciliation(self):
        self.assertTrue(self.orders.reserve("entry", **self.order))
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE reservations SET payload=? WHERE order_id=?",
                       (json.dumps({"symbol": "BTC/USD", "strategy_id": "momentum-v1",
                                    "price": 100, "stop_price": 95, "quantity": 1,
                                    "notional": 600, "risk": 5}), "entry"))
        with self.assertRaises(ValueError):
            PersistentPaperDesk(self.path)

    def test_corrupt_state_fails_closed(self):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE state SET payload=?", (json.dumps({
                "cash_usd": float("nan"), "day_start_equity_usd": 500,
                "daily_realized_pnl_usd": 0, "kill_switch": False,
                "marks": {}, "positions": []
            }),))
        with self.assertRaises(ValueError):
            PersistentPaperDesk(self.path)

    def test_event_log_tracks_changes(self):
        self.assertTrue(self.orders.reserve("entry", **self.order))
        self.assertTrue(self.orders.fill("entry", strategy_authorized=True, market_data_fresh=True, expected_strategy_id="momentum-v1", expected_symbol="BTC/USD"))
        with sqlite3.connect(self.path) as db:
            events = [row[0] for row in db.execute("SELECT kind FROM events ORDER BY seq")]
        self.assertEqual(events, ["initialize", "mark", "reserve", "fill"])


if __name__ == "__main__":
    unittest.main()
