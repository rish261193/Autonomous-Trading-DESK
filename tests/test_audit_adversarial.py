"""Independent audit adversarial tests (docs/independent-audit/03, 05).

Each test asserts the SAFE behaviour. Tests decorated with
``@unittest.expectedFailure`` document a defect that is still OPEN; the
finding ID in the docstring maps to docs/independent-audit/03. If one of
them starts passing, unittest reports an "unexpected success" and the
decorator must be removed deliberately.
"""
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_desk.agent_contracts import AgentEvent, AgentResponse, EventType, Role
from trading_desk.orchestrator import Orchestrator
from trading_desk.paper_controller import GuardedPaperController, PriceObservation
from trading_desk.paper_stops import process_stop_observation
from trading_desk.pending_orders import PendingOrders
from trading_desk.persistent_paper import PersistentPaperDesk

T0 = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)


class Clock:
    """Deterministic trusted clock injected at desk construction."""

    def __init__(self, value=T0):
        self.value = value

    def __call__(self):
        return self.value


def fill(orders, order_id, strategy_id="approved-v1", symbol="BTC/USD"):
    return orders.fill(order_id, strategy_authorized=True, market_data_fresh=True,
                       expected_strategy_id=strategy_id, expected_symbol=symbol)


class AuditBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "ledger.sqlite")
        self.clock = Clock()
        self.desk = PersistentPaperDesk(self.path, clock=self.clock)
        self.orders = PendingOrders(self.desk)
        self.control = GuardedPaperController(self.desk, frozenset({"approved-v1"}))
        self.order = dict(strategy_id="approved-v1", symbol="BTC/USD", price=100,
                          stop_price=95, quantity=1, strategy_authorized=True,
                          market_data_fresh=True)

    def obs(self, price, symbol="BTC/USD", age=0):
        return PriceObservation(symbol, price, self.clock() - timedelta(seconds=age))

    def enter(self, order_id="e", **change):
        order = self.order | change
        self.desk.mark(order["symbol"], order["price"])
        self.assertTrue(self.orders.reserve(order_id, **order))
        self.assertTrue(fill(self.orders, order_id, order["strategy_id"], order["symbol"]))

    def restart(self):
        return PersistentPaperDesk(self.path, clock=self.clock)


class TrustBoundaryTests(AuditBase):
    @unittest.expectedFailure
    def test_a01_unapproved_strategy_cannot_fill_through_pending_orders(self):
        """OPEN F-01: PendingOrders trusts caller-supplied authorization booleans."""
        self.desk.mark("BTC/USD", 100)
        self.assertFalse(self.orders.reserve("x", **(self.order | {"strategy_id": "rogue"})))

    @unittest.expectedFailure
    def test_a02_implausible_price_is_rejected(self):
        """OPEN F-02: no price-plausibility check or authenticated feed."""
        self.assertFalse(self.control.observe(self.obs(1e9), now=self.clock()))

    @unittest.expectedFailure
    def test_a03_fabricated_mark_cannot_realize_profit(self):
        """OPEN F-02: a forged mark followed by close books fictitious P&L."""
        self.enter()
        self.desk.mark("BTC/USD", 1_000_000)
        self.assertLess(self.desk.close(0, 1_000_000), 1_000)

    @unittest.expectedFailure
    def test_a08_reservation_fillable_after_small_price_move(self):
        """OPEN F-09: fills require mark == reserved price exactly (liveness)."""
        self.assertTrue(self.control.reserve(
            "r", strategy_id="approved-v1", symbol="BTC/USD", price=100,
            stop_price=95, quantity=1, observation=self.obs(100), now=self.clock()))
        moved = self.obs(100.01)
        self.assertTrue(self.control.observe(moved, now=self.clock()))
        self.assertTrue(self.control.fill("r", strategy_id="approved-v1",
                                          observation=moved, now=self.clock()))


class StopIntegrityTests(AuditBase):
    def test_a04_any_mark_through_stop_closes_position(self):
        """FIXED F-03: observe()/mark() used to skip stop evaluation."""
        self.enter()
        self.assertTrue(self.control.observe(self.obs(80), now=self.clock()))
        state = self.desk.snapshot()
        self.assertEqual(state.positions, [])
        self.assertEqual(state.cash_usd, 480)

    def test_a05_gap_can_exceed_daily_threshold_but_new_risk_is_refused(self):
        """Characterization F-05: refusing new risk is not a loss guarantee."""
        self.desk.mark("ETH/USD", 100)
        self.enter("b", stop_price=99, quantity=2.5)
        self.enter("e", symbol="ETH/USD", stop_price=99, quantity=2.4)
        self.desk.apply_stop_mark("BTC/USD", 93)
        self.desk.apply_stop_mark("ETH/USD", 92)
        state = self.desk.snapshot()
        loss = 500 - state.equity()
        self.assertGreater(loss, 15)            # 3% of 500 exceeded by the gap
        self.assertAlmostEqual(loss, 36.7)       # 7.34% with only 0.98% planned risk
        self.desk.mark("BTC/USD", 93)
        self.assertFalse(self.orders.reserve("after", **(self.order | {
            "price": 93, "stop_price": 92.9, "quantity": 0.1})))


class ReservationTests(AuditBase):
    def test_reserve_refuses_cash_over_commitment(self):
        """Added after mutation testing: removing the reserve-time cash check
        previously left the whole suite green (fills caught it later)."""
        self.desk.mark("BTC/USD", 100)
        small_risk = self.order | {"stop_price": 99.99, "quantity": 2}
        self.assertTrue(self.orders.reserve("r1", **small_risk))
        self.assertTrue(self.orders.reserve("r2", **small_risk))
        self.assertFalse(self.orders.reserve("r3", **small_risk))   # 600 > 500 cash


class ClockTests(AuditBase):
    def test_a06_arbitrary_caller_clock_rejected(self):
        """FIXED F-06: restores guard added in 6607789 and reverted in d6072a6."""
        with self.assertRaises(ValueError):
            self.desk.roll_utc_day(now=datetime(2099, 1, 1, tzinfo=timezone.utc))
        self.desk.mark("BTC/USD", 100)
        self.assertTrue(self.orders.reserve("ok", **self.order))

    def test_a06b_controller_rejects_forged_now(self):
        """FIXED F-06: freshness is measured against the trusted clock."""
        far = self.clock() + timedelta(days=30)
        observation = PriceObservation("BTC/USD", 100, far)
        self.assertFalse(self.control.observe(observation, now=far))

    def test_a14_restart_after_utc_midnight_rolls_once(self):
        self.enter()
        self.desk.mark("BTC/USD", 98)
        self.clock.value = T0 + timedelta(hours=13)   # 01:00 UTC next day
        restarted = self.restart()
        self.assertTrue(restarted.roll_utc_day())
        self.assertFalse(restarted.roll_utc_day())
        state = restarted.snapshot()
        self.assertEqual(state.day_start_equity_usd, 498)
        self.assertEqual(len(state.positions), 1)


class LedgerIntegrityTests(AuditBase):
    def _edit_state(self, **changes):
        with sqlite3.connect(self.path) as db:
            payload = json.loads(db.execute("SELECT payload FROM state").fetchone()[0])
            payload.update(changes)
            db.execute("UPDATE state SET payload=?", (json.dumps(payload),))

    def test_a07_tampered_cash_detected_at_restart(self):
        """FIXED F-07: snapshot/event replay verification."""
        self.enter()
        self._edit_state(cash_usd=1_000_000)
        with self.assertRaises(ValueError):
            self.restart()

    def test_a07b_tampered_daily_baseline_detected(self):
        self.enter()
        self._edit_state(day_start_equity_usd=1_000_000)
        with self.assertRaises(ValueError):
            self.restart()

    def test_a07c_deleted_event_detected(self):
        self.enter()
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM events WHERE kind='mark'")
        with self.assertRaises(ValueError):
            self.restart()

    def test_a07d_edited_event_detected(self):
        self.enter()
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE events SET payload=replace(payload, '100', '99') WHERE kind='mark'")
        with self.assertRaises(ValueError):
            self.restart()

    def test_a07e_valid_ledger_verifies_and_exposes_anchor(self):
        self.enter()
        self.desk.mark("BTC/USD", 101)
        self.desk.close_position("e", 101)
        report = self.restart().verify_integrity()
        self.assertGreaterEqual(report["events"], 5)
        self.assertEqual(len(report["head_hash"]), 64)

    def test_a11_events_are_timestamped(self):
        self.enter()
        with sqlite3.connect(self.path) as db:
            stamps = [r[0] for r in db.execute("SELECT created_at_utc FROM events")]
        self.assertTrue(stamps)
        self.assertTrue(all(s and s.endswith("+00:00") for s in stamps))


class AttributionTests(AuditBase):
    def test_a09_close_by_order_id_survives_concurrent_index_shift(self):
        """FIXED F-08: index-based close could close the wrong position."""
        self.enter("A", stop_price=98, quantity=1.0)
        self.enter("B", stop_price=96, quantity=0.5)
        self.enter("C", stop_price=90, quantity=0.1)
        self.desk.apply_stop_mark("BTC/USD", 97.5)        # stops A, shifts indices
        self.desk.close_position("B", 97.5)
        remaining = [p.order_id for p in self.desk.snapshot().positions]
        self.assertEqual(remaining, ["C"])

    def test_a10_positions_and_exits_carry_strategy_attribution(self):
        self.enter()
        position = self.desk.snapshot().positions[0]
        self.assertEqual((position.strategy_id, position.order_id), ("approved-v1", "e"))
        self.desk.apply_stop_mark("BTC/USD", 90)
        with sqlite3.connect(self.path) as db:
            payload = json.loads(db.execute(
                "SELECT payload FROM events WHERE kind='stop_mark' ORDER BY seq DESC").fetchone()[0])
        self.assertEqual(payload["exits"], [{"order_id": "e", "strategy_id": "approved-v1",
                                              "realized_pnl_usd": -10}])


class KillSwitchTests(AuditBase):
    def test_a13_kill_switch_blocks_entries_while_database_locked(self):
        """FIXED F-10: halt() used to fail after 10 s if another writer held the lock."""
        self.desk.mark("BTC/USD", 100)
        blocker = sqlite3.connect(self.path, isolation_level=None)
        blocker.execute("BEGIN IMMEDIATE")
        outcome = {}
        thread = threading.Thread(target=lambda: outcome.setdefault(
            "halt", self._halt_catching()))
        thread.start()
        deadline = time.time() + 5
        while not self.desk.halt_requested() and time.time() < deadline:
            time.sleep(0.01)
        started = time.time()
        refused = self.orders.reserve("blocked", **self.order) is False
        elapsed = time.time() - started
        blocker.rollback()
        blocker.close()
        thread.join()
        self.assertTrue(refused)
        self.assertLess(elapsed, 1.0)
        self.assertTrue(self.restart().snapshot().kill_switch)

    def _halt_catching(self):
        try:
            return self.desk.halt()
        except sqlite3.OperationalError as exc:
            return exc


class OrchestratorSpoofTests(unittest.TestCase):
    def test_a12_handler_cannot_spoof_another_producer(self):
        """FIXED F-12: router now binds proposed producer to responding role."""
        router = Orchestrator()

        def bull(event):
            forged = AgentEvent(EventType.STRATEGY_AUTHORIZED, Role.PORTFOLIO_MANAGER,
                                {"strategy_id": "rogue"})
            return AgentResponse(Role.BULL_AGENT, event.event_id, "x",
                                 proposed_events=(forged,))

        router.subscribe(EventType.RESEARCH_REQUESTED, Role.BULL_AGENT, bull)
        with self.assertRaises(ValueError):
            router.run(AgentEvent(EventType.RESEARCH_REQUESTED, Role.MARKET_INTELLIGENCE))


if __name__ == "__main__":
    unittest.main()
