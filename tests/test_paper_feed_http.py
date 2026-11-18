"""Offline tests for public-feed parsing and paper intent HTTP validation."""
import io
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from datetime import datetime, timezone

from trading_desk.kraken_public_prices import KrakenPublicPriceSource
from trading_desk.paper_intent_http import serve_paper_intents


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()


class FeedTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 18, tzinfo=timezone.utc)

    def source(self, payload):
        return KrakenPublicPriceSource(
            opener=lambda url, timeout: FakeResponse(json.dumps(payload).encode()),
            clock=lambda: self.now)

    def test_valid_btc_quote(self):
        obs = self.source({"error": [], "result": {
            "XXBTZUSD": {"c": ["90000.50", "1"]}}})("BTC/USD")
        self.assertEqual(obs.price, 90000.5)
        self.assertEqual(obs.timestamp, self.now)

    def test_reject_unexpected_pair(self):
        with self.assertRaises(ValueError):
            self.source({"error": [], "result": {
                "XETHZUSD": {"c": ["90000", "1"]}}})("BTC/USD")

    def test_reject_invalid_and_nonfinite_prices(self):
        for value in ("nan", "-1", "inf", "oops"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.source({"error": [], "result": {
                    "XXBTZUSD": {"c": [value]}}})("BTC/USD")

    def test_reject_exchange_error(self):
        with self.assertRaises(ValueError):
            self.source({"error": ["EGeneral:Invalid arguments"],
                         "result": {}})("BTC/USD")


class StubService:
    def submit(self, intent):
        return intent.strategy_id == "approved"


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.server = serve_paper_intents(StubService(), port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.thread.join)
        self.url = "http://127.0.0.1:%d/v1/paper/intents" % self.server.server_port

    def post(self, payload):
        req = Request(self.url, data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=3) as response:
                return response.status
        except HTTPError as error:
            return error.code

    def test_accept_intent_only(self):
        self.assertEqual(self.post({"order_id": "1", "strategy_id": "approved",
            "symbol": "BTC/USD", "quantity": 1, "stop_price": 95}), 200)

    def test_reject_injected_authorization_or_price(self):
        self.assertEqual(self.post({"order_id": "1", "strategy_id": "approved",
            "symbol": "BTC/USD", "quantity": 1, "stop_price": 95,
            "strategy_authorized": True, "price": 1e9}), 400)

    def test_reject_unapproved_strategy(self):
        self.assertEqual(self.post({"order_id": "1", "strategy_id": "rogue",
            "symbol": "BTC/USD", "quantity": 1, "stop_price": 95}), 403)

    def test_nonloopback_rejected(self):
        with self.assertRaises(ValueError):
            serve_paper_intents(StubService(), host="0.0.0.0", port=0)


if __name__ == "__main__":
    unittest.main()
