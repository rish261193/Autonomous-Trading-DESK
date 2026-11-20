"""Independent audit: fault injection, crash recovery, multi-process
concurrency, randomized accounting invariants and deterministic replay.

These tests use real processes and SIGKILL where noted (POSIX only).
See docs/independent-audit/05_TEST_RESULTS.md.
"""
import os
import random
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_desk.pending_orders import PendingOrders
from trading_desk.persistent_paper import PersistentPaperDesk

T0 = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
SMALL = dict(strategy_id="s", symbol="BTC/USD", price=100, stop_price=99.99,
             quantity=0.01, strategy_authorized=True, market_data_fresh=True)


class Clock:
    def __init__(self, value=T0):
        self.value = value

    def __call__(self):
        return self.value


def fill(orders, order_id, strategy_id="s", symbol="BTC/USD"):
    return orders.fill(order_id, strategy_authorized=True, market_data_fresh=True,
                       expected_strategy_id=strategy_id, expected_symbol=symbol)


def open_risk(desk):
    return sum(max(0.0, max(p.entry_price, desk.marks[p.symbol]) - p.stop_price)
               * p.quantity for p in desk.positions)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "ledger.sqlite")


class FaultInjectionTests(Base):
    def setUp(self):
        super().setUp()
        self.clock = Clock()
        self.desk = PersistentPaperDesk(self.path, clock=self.clock)
        self.desk.mark("BTC/USD", 100)
        self.orders = PendingOrders(self.desk)

    def _fail_on(self, kind):
        original = self.desk._event

        def failing(db, event_kind, payload):
            if event_kind == kind:
                raise RuntimeError(f"injected failure before commit of {kind}")
            return original(db, event_kind, payload)
        self.desk._event = failing
        return lambda: setattr(self.desk, "_event", original)

    def test_failure_inside_fill_rolls_back_everything(self):
        self.assertTrue(self.orders.reserve("a", **SMALL))
        restore = self._fail_on("fill")
        with self.assertRaises(RuntimeError):
            fill(self.orders, "a")
        restore()
        state = self.desk.snapshot()
        self.assertEqual((state.cash_usd, state.positions), (500, []))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT status FROM reservations").fetchone()[0],
                             "pending")
        self.assertTrue(fill(self.orders, "a"))
        self.desk.verify_integrity()

    def test_failure_inside_close_rolls_back_everything(self):
        self.assertTrue(self.orders.reserve("a", **SMALL))
        self.assertTrue(fill(self.orders, "a"))
        restore = self._fail_on("close")
        with self.assertRaises(RuntimeError):
            self.desk.close_position("a", 100)
        restore()
        self.assertEqual(len(self.desk.snapshot().positions), 1)
        self.desk.verify_integrity()

    def test_database_unavailable_never_approves_and_halt_still_blocks(self):
        os.replace(self.path, self.path + ".moved")   # database disappears
        with self.assertRaises(sqlite3.Error):
            self.orders.reserve("x", **SMALL)
        with self.assertRaises(sqlite3.Error):
            self.desk.halt()                            # DB write fails ...
        self.assertTrue(self.desk.halt_requested())    # ... flag still set
        os.replace(self.path + ".moved", self.path)
        self.assertFalse(self.orders.reserve("y", **SMALL))
        self.assertTrue(PersistentPaperDesk(self.path, clock=self.clock)
                        .snapshot().kill_switch)


WORKER = r"""
import sys, os
from trading_desk.persistent_paper import PersistentPaperDesk
from trading_desk.pending_orders import PendingOrders
path, tag = sys.argv[1], sys.argv[2]
desk = PersistentPaperDesk(path)
orders = PendingOrders(desk)
order = dict(strategy_id="s", symbol="BTC/USD", price=100, stop_price=99.99,
             quantity=0.01, strategy_authorized=True, market_data_fresh=True)
i = 0
while True:
    oid = f"{tag}-{i}"
    if orders.reserve(oid, **order):
        orders.fill(oid, strategy_authorized=True, market_data_fresh=True,
                    expected_strategy_id="s", expected_symbol="BTC/USD")
    if i % 3 == 2:
        positions = desk.snapshot().positions
        if positions:
            try:
                desk.close_position(positions[0].order_id, 100)
            except ValueError:
                pass  # closed concurrently by another worker
    i += 1
"""

RACER = r"""
import sys, time
from trading_desk.persistent_paper import PersistentPaperDesk
from trading_desk.pending_orders import PendingOrders
path, order_id, start = sys.argv[1], sys.argv[2], float(sys.argv[3])
orders = PendingOrders(PersistentPaperDesk(path))
while time.time() < start:
    time.sleep(0.001)
ok = orders.reserve(order_id, strategy_id="s", symbol="BTC/USD", price=100,
                    stop_price=95, quantity=1, strategy_authorized=True,
                    market_data_fresh=True)
print("1" if ok else "0")
"""


@unittest.skipUnless(os.name == "posix", "requires POSIX signals")
class CrashAndProcessConcurrencyTests(Base):
    def _check_invariants(self, desk):
        desk.verify_integrity()                     # chain + replay == snapshot
        state = desk.snapshot()
        held = sum(p.quantity * p.entry_price for p in state.positions)
        self.assertAlmostEqual(state.cash_usd + held, 500, places=6)
        self.assertGreaterEqual(state.cash_usd, -1e-9)

    def test_sigkill_during_trading_never_corrupts_ledger(self):
        desk = PersistentPaperDesk(self.path)
        desk.mark("BTC/USD", 100)
        rng = random.Random(2026)
        for round_number in range(6):
            workers = [subprocess.Popen([sys.executable, "-c", WORKER, self.path,
                                         f"r{round_number}w{w}"])
                       for w in range(2)]
            time.sleep(0.15 + rng.random() * 0.25)
            for worker in workers:
                worker.send_signal(signal.SIGKILL)
                worker.wait()
            restarted = PersistentPaperDesk(self.path)  # reconcile() on startup
            self._check_invariants(restarted)
        with sqlite3.connect(self.path) as db:
            fills = db.execute("SELECT count(*) FROM events WHERE kind='fill'").fetchone()[0]
        self.assertGreater(fills, 0, "workers made no progress; test proves nothing")

    def test_parallel_processes_cannot_exceed_combined_risk(self):
        PersistentPaperDesk(self.path).mark("BTC/USD", 100)
        start = time.time() + 1.5
        procs = [subprocess.Popen([sys.executable, "-c", RACER, self.path, f"o{i}",
                                   str(start)], stdout=subprocess.PIPE, text=True)
                 for i in range(6)]
        outcomes = [p.communicate(timeout=60)[0].strip() for p in procs]
        self.assertEqual(outcomes.count("1"), 1, outcomes)

    def test_parallel_processes_cannot_reuse_order_id(self):
        PersistentPaperDesk(self.path).mark("BTC/USD", 100)
        start = time.time() + 1.5
        procs = [subprocess.Popen([sys.executable, "-c", RACER, self.path, "same-id",
                                   str(start)], stdout=subprocess.PIPE, text=True)
                 for _ in range(6)]
        outcomes = [p.communicate(timeout=60)[0].strip() for p in procs]
        self.assertEqual(outcomes.count("1"), 1, outcomes)


class RandomizedInvariantTests(Base):
    """Seeded random operation sequences (stdlib-only property testing)."""

    def run_sequence(self, path, seed, steps=150):
        rng = random.Random(seed)
        clock = Clock()
        desk = PersistentPaperDesk(path, clock=clock)
        orders = PendingOrders(desk)
        price = {"BTC/USD": 100.0, "ETH/USD": 50.0}
        for symbol, value in price.items():
            desk.mark(symbol, value)
        pending, opened = [], []
        for step in range(steps):
            state = desk.snapshot()
            equity = state.equity()
            breached = equity - state.day_start_equity_usd <= -0.03 * state.day_start_equity_usd
            op = rng.choice(("mark", "mark", "reserve", "fill", "cancel", "close", "day"))
            symbol = rng.choice(tuple(price))
            if op == "mark":
                price[symbol] = round(price[symbol] * (1 + rng.uniform(-0.04, 0.04)), 6)
                desk.mark(symbol, price[symbol])
            elif op == "reserve":
                stop = round(price[symbol] * (1 - rng.uniform(0.002, 0.05)), 6)
                qty = round(rng.uniform(0.01, 2.0) * 50 / price[symbol], 6)
                oid = f"{seed}-{step}"
                ok = orders.reserve(oid, strategy_id="s", symbol=symbol,
                                    price=price[symbol], stop_price=stop, quantity=qty,
                                    strategy_authorized=True, market_data_fresh=True)
                if breached:
                    self.assertFalse(ok, "entry accepted after daily-loss breach")
                if ok:
                    pending.append((oid, symbol))
            elif op == "fill" and pending:
                oid, sym = pending.pop(rng.randrange(len(pending)))
                if fill(orders, oid, symbol=sym):
                    opened.append(oid)
                    after = desk.snapshot()
                    self.assertLessEqual(open_risk(after), 0.01 * after.equity() + 1e-9)
                    self.assertFalse(breached, "fill accepted after daily-loss breach")
                else:
                    orders.cancel(oid)
            elif op == "cancel" and pending:
                orders.cancel(pending.pop(rng.randrange(len(pending)))[0])
            elif op == "close":
                live = [p for p in desk.snapshot().positions]
                if live:
                    target = rng.choice(live)
                    desk.close_position(target.order_id, price[target.symbol])
            elif op == "day":
                clock.value += timedelta(hours=rng.choice((3, 9, 25)))
                desk.roll_utc_day()
            self.assert_invariants(desk)
        return desk

    def assert_invariants(self, desk):
        state = desk.snapshot()
        self.assertGreaterEqual(state.cash_usd, -1e-9)
        for p in state.positions:
            self.assertAlmostEqual(p.risk_usd, (p.entry_price - p.stop_price) * p.quantity)
            self.assertGreater(p.stop_price, 0)
            self.assertGreater(state.marks[p.symbol], p.stop_price)   # stops honored
        marked = state.cash_usd + sum(p.quantity * state.marks[p.symbol]
                                      for p in state.positions)
        self.assertAlmostEqual(state.equity(), marked)

    def test_random_sequences_preserve_accounting_invariants(self):
        for seed in range(12):
            with self.subTest(seed=seed):
                desk = self.run_sequence(str(Path(self.tmp.name) / f"s{seed}.sqlite"), seed)
                desk.verify_integrity()

    def test_deterministic_replay_produces_identical_ledger(self):
        a = self.run_sequence(str(Path(self.tmp.name) / "a.sqlite"), 99)
        b = self.run_sequence(str(Path(self.tmp.name) / "b.sqlite"), 99)
        self.assertEqual(a.snapshot().__dict__, b.snapshot().__dict__)
        self.assertEqual(a.ledger_head(), b.ledger_head())


class PerformanceTests(Base):
    def test_ledger_throughput_and_startup_verification_budget(self):
        desk = PersistentPaperDesk(self.path, clock=Clock())
        desk.mark("BTC/USD", 100)
        orders = PendingOrders(desk)
        started = time.perf_counter()
        for i in range(150):
            self.assertTrue(orders.reserve(str(i), **SMALL))
            self.assertTrue(fill(orders, str(i)))
        trading = time.perf_counter() - started
        started = time.perf_counter()
        PersistentPaperDesk(self.path, clock=Clock())          # full replay
        startup = time.perf_counter() - started
        self.assertLess(trading, 10.0)
        self.assertLess(startup, 5.0)


if __name__ == "__main__":
    unittest.main()
