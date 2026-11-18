"""Deterministic tests for two-source quote validation."""
import unittest
from datetime import datetime, timedelta, timezone

from trading_desk.corroborated_prices import CorroboratedPriceSource
from trading_desk.paper_controller import PriceObservation


class CrossCheckTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 18, 20, tzinfo=timezone.utc)
        self.first = PriceObservation("BTC/USD", 100, self.now)
        self.second = PriceObservation("BTC/USD", 100.2, self.now)
        self.feed = CorroboratedPriceSource(
            lambda symbol: self.first, lambda symbol: self.second,
            clock=lambda: self.now)

    def test_accept_close_independent_quotes(self):
        self.assertEqual(self.feed("BTC/USD"), self.first)

    def test_reject_price_outlier(self):
        self.second = PriceObservation("BTC/USD", 110, self.now)
        with self.assertRaises(ValueError):
            self.feed("BTC/USD")

    def test_reject_stale_feed(self):
        self.second = PriceObservation(
            "BTC/USD", 100, self.now - timedelta(seconds=20))
        with self.assertRaises(ValueError):
            self.feed("BTC/USD")

    def test_reject_wrong_instrument(self):
        self.second = PriceObservation("ETH/USD", 100, self.now)
        with self.assertRaises(ValueError):
            self.feed("BTC/USD")

    def test_reject_regressed_timestamp(self):
        self.feed("BTC/USD")
        self.now += timedelta(seconds=1)
        self.first = PriceObservation(
            "BTC/USD", 100, self.now - timedelta(seconds=1))
        self.second = PriceObservation("BTC/USD", 100.1, self.now)
        self.feed("BTC/USD")
        self.first = PriceObservation(
            "BTC/USD", 100, self.now - timedelta(seconds=2))
        with self.assertRaises(ValueError):
            self.feed("BTC/USD")

    def test_reject_outage(self):
        feed = CorroboratedPriceSource(
            lambda symbol: self.first,
            lambda symbol: (_ for _ in ()).throw(ConnectionError()),
            clock=lambda: self.now)
        with self.assertRaises(ConnectionError):
            feed("BTC/USD")


if __name__ == "__main__":
    unittest.main()
