"""End-to-end safety composition smoke test without network calls."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from trading_desk.paper_controller import PriceObservation
from trading_desk.paper_safety_composition import build_guarded_paper_service
from trading_desk.persistent_paper import PersistentPaperDesk
from trading_desk.trusted_paper_intents import PaperBuyIntent


class PaperSafetyCompositionTests(unittest.TestCase):
    def test_market_data_outage_halts_ledger_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "desk.sqlite")
            now = datetime(2026, 11, 18, tzinfo=timezone.utc)
            desk = PersistentPaperDesk(path, clock=lambda: now)
            def outage(symbol):
                raise ConnectionError("source offline")
            service = build_guarded_paper_service(
                desk, approved_strategies=frozenset({"approved"}),
                primary_source=outage, secondary_source=outage,
                failure_threshold=2)
            intent = PaperBuyIntent("order1", "approved", "BTC/USD", 0.01, 90)
            self.assertFalse(service.submit(intent))
            self.assertFalse(service.submit(intent))
            self.assertTrue(desk.halt_requested())
            self.assertTrue(PersistentPaperDesk(
                path, clock=lambda: now).snapshot().kill_switch)
            self.assertFalse(service.submit(intent))

    def test_recovered_feed_triggers_stop_while_entries_remain_halted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "desk.sqlite")
            now = datetime(2026, 11, 18, tzinfo=timezone.utc)
            desk = PersistentPaperDesk(path, clock=lambda: now)
            state = {"price": 100.0, "offline": False}
            def primary(symbol):
                if state["offline"]:
                    raise ConnectionError("primary offline")
                return PriceObservation(symbol, state["price"], now)
            def secondary(symbol):
                if state["offline"]:
                    raise ConnectionError("secondary offline")
                return PriceObservation(symbol, state["price"], now)
            service = build_guarded_paper_service(
                desk, approved_strategies=frozenset({"approved"}),
                primary_source=primary, secondary_source=secondary,
                failure_threshold=2)
            intent = PaperBuyIntent("stop-test", "approved", "BTC/USD", 0.01, 95.0)
            self.assertTrue(service.submit(intent))
            self.assertTrue(service.fill("stop-test", strategy_id="approved",
                                         symbol="BTC/USD"))
            self.assertEqual(len(desk.snapshot().positions), 1)
            state["offline"] = True
            self.assertFalse(service.observe("BTC/USD"))
            self.assertFalse(service.observe("BTC/USD"))
            self.assertTrue(desk.halt_requested())
            state["offline"] = False
            state["price"] = 80.0
            self.assertTrue(service.observe("BTC/USD"))
            self.assertEqual(len(desk.snapshot().positions), 0)
            self.assertTrue(desk.snapshot().kill_switch)
            self.assertFalse(service.submit(
                PaperBuyIntent("blocked", "approved", "BTC/USD", 0.01, 70.0)))
            self.assertEqual(len(PersistentPaperDesk(
                path, clock=lambda: now).snapshot().positions), 0)

    def test_corrobated_prices_allow_paper_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 11, 18, tzinfo=timezone.utc)
            desk = PersistentPaperDesk(
                str(Path(directory) / "desk.sqlite"), clock=lambda: now)
            primary = lambda symbol: PriceObservation(symbol, 100, now)
            secondary = lambda symbol: PriceObservation(symbol, 100.1, now)
            service = build_guarded_paper_service(
                desk, approved_strategies=frozenset({"approved"}),
                primary_source=primary, secondary_source=secondary)
            self.assertTrue(service.submit(
                PaperBuyIntent("order1", "approved", "BTC/USD", 1, 99)))
            self.assertFalse(desk.snapshot().kill_switch)


if __name__ == "__main__":
    unittest.main()
