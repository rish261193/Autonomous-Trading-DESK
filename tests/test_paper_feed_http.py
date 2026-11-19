"""Offline tests for public-feed parsing and paper intent HTTP validation."""
import io
import json
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from datetime import datetime, timezone

from trading_desk.kraken_public_prices import KrakenPublicPriceSource
from trading_desk.paper_intent_http import serve_paper_intents, sign_intent


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
        self.secret = b's' * 32
        self.server = serve_paper_intents(StubService(), secret=self.secret, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        # unittest cleanups execute in LIFO order: stop the server before join.
        self.addCleanup(self.thread.join, timeout=5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = "http://127.0.0.1:%d/v1/paper/intents" % self.server.server_port

    def post(self, payload):
        body = json.dumps(payload).encode()
        stamp = int(time.time())
        nonce = "abcdef0123456789"
        req = Request(self.url, data=body,
                      headers={"Content-Type": "application/json",
                               "X-Paper-Timestamp": str(stamp),
                               "X-Paper-Nonce": nonce,
                               "X-Paper-Signature": sign_intent(self.secret, stamp, nonce, body)})
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

    def test_unsigned_request_rejected(self):
        req = Request(self.url, data=b"{}", method="POST")
        with self.assertRaises(HTTPError) as context:
            urlopen(req, timeout=3)
        self.assertEqual(context.exception.code, 401)

    def test_replay_rejected(self):
        self.assertEqual(self.post({"order_id": "1", "strategy_id": "approved",
            "symbol": "BTC/USD", "quantity": 1, "stop_price": 95}), 200)
        self.assertEqual(self.post({"order_id": "2", "strategy_id": "approved",
            "symbol": "BTC/USD", "quantity": 1, "stop_price": 95}), 409)

    def test_nonloopback_rejected(self):
        with self.assertRaises(ValueError):
            serve_paper_intents(StubService(), secret=self.secret, host="0.0.0.0", port=0)


if __name__ == "__main__":
    unittest.main()
