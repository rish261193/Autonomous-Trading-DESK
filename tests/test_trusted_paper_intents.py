"""Audit F-01/F-02: strategy inputs cannot set authority or market prices."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_desk.paper_controller import PriceObservation
from trading_desk.persistent_paper import PersistentPaperDesk
from trading_desk.trusted_paper_intents import PaperBuyIntent, TrustedPaperIntentService


class TrustedPaperIntentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
        self.price = 100.0
        self.timestamp = self.now
        self.symbol = "BTC/USD"
        self.desk = PersistentPaperDesk(
            str(Path(self.tmp.name) / "paper.sqlite"), clock=lambda: self.now)
        self.service = TrustedPaperIntentService(
            self.desk, approved_strategies=frozenset({"approved"}),
            price_source=lambda symbol: PriceObservation(
                self.symbol, self.price, self.timestamp))
        self.intent = PaperBuyIntent("order1", "approved", "BTC/USD", 1, 95)

    def test_authorized_intent_uses_feed_price_and_fills(self):
        self.assertTrue(self.service.submit(self.intent))
        self.assertTrue(self.service.fill(
            "order1", strategy_id="approved", symbol="BTC/USD"))
        self.assertEqual(len(self.desk.snapshot().positions), 1)

    def test_rogue_strategy_cannot_self_authorize(self):
        self.assertFalse(self.service.submit(
            PaperBuyIntent("rogue", "rogue", "BTC/USD", 1, 95)))

    def test_intent_has_no_market_price_or_authorization_field(self):
        with self.assertRaises(TypeError):
            PaperBuyIntent("x", "approved", "BTC/USD", 1, 95,
                           strategy_authorized=True)
        with self.assertRaises(TypeError):
            PaperBuyIntent("x", "approved", "BTC/USD", 1, 95,
                           price=1_000_000)

    def test_stale_feed_fails_closed(self):
        self.timestamp = self.now - timedelta(minutes=2)
        self.assertFalse(self.service.submit(self.intent))

    def test_wrong_symbol_feed_fails_closed(self):
        self.symbol = "ETH/USD"
        self.assertFalse(self.service.submit(self.intent))

    def test_feed_outage_fails_closed(self):
        service = TrustedPaperIntentService(
            self.desk, approved_strategies=frozenset({"approved"}),
            price_source=lambda symbol: (_ for _ in ()).throw(RuntimeError("down")))
        self.assertFalse(service.submit(self.intent))

    def test_fill_rechecks_current_trusted_price(self):
        self.assertTrue(self.service.submit(self.intent))
        self.price = 101
        self.assertFalse(self.service.fill(
            "order1", strategy_id="approved", symbol="BTC/USD"))

    def test_untrusted_intent_cannot_exceed_risk(self):
        self.assertFalse(self.service.submit(
            PaperBuyIntent("oversized", "approved", "BTC/USD", 10, 95)))


if __name__ == "__main__":
    unittest.main()
