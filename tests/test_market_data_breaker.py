"""Circuit-breaker regression tests: halt, recovery, concurrency and isolation."""
import threading
import tempfile
import unittest
from pathlib import Path
from trading_desk.persistent_paper import PersistentPaperDesk

from trading_desk.market_data_breaker import MarketDataCircuitBreaker, MarketDataHalted


class BreakerTests(unittest.TestCase):
    def test_halts_after_repeated_feed_errors(self):
        calls = []
        def failed(symbol):
            calls.append(symbol)
            raise ConnectionError("feed down")
        breaker = MarketDataCircuitBreaker(failed, failure_threshold=2)
        for _ in range(2):
            with self.assertRaises(ConnectionError):
                breaker("BTC/USD")
        self.assertTrue(breaker.halted)
        with self.assertRaises(MarketDataHalted):
            breaker("BTC/USD")
        self.assertEqual(len(calls), 2)

    def test_success_resets_consecutive_failure_count(self):
        sequence = [ConnectionError("x"), 100, ConnectionError("y"), 101]
        def source(symbol):
            value = sequence.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        breaker = MarketDataCircuitBreaker(source, failure_threshold=2)
        with self.assertRaises(ConnectionError):
            breaker("BTC/USD")
        self.assertEqual(breaker("BTC/USD"), 100)
        with self.assertRaises(ConnectionError):
            breaker("BTC/USD")
        self.assertFalse(breaker.halted)
        self.assertEqual(breaker("BTC/USD"), 101)

    def test_healthy_btc_does_not_mask_eth_outage(self):
        halted = []
        def source(symbol):
            if symbol == "ETH/USD":
                raise ConnectionError("ETH feed unavailable")
            return 100.0
        breaker = MarketDataCircuitBreaker(
            source, failure_threshold=3, on_halt=lambda: halted.append(True))
        for _ in range(2):
            with self.assertRaises(ConnectionError):
                breaker("ETH/USD")
            self.assertEqual(breaker("BTC/USD"), 100.0)
            self.assertFalse(breaker.halted)
        with self.assertRaises(ConnectionError):
            breaker("ETH/USD")
        self.assertTrue(breaker.halted)
        self.assertEqual(halted, [True])
        with self.assertRaises(MarketDataHalted):
            breaker("BTC/USD")

    def test_success_resets_only_its_own_symbol_streak(self):
        attempts = {"ETH/USD": 0}
        def source(symbol):
            if symbol == "ETH/USD":
                attempts[symbol] += 1
                if attempts[symbol] in (1, 2, 4):
                    raise ConnectionError("intermittent ETH failure")
            return 100.0
        breaker = MarketDataCircuitBreaker(source, failure_threshold=3)
        with self.assertRaises(ConnectionError):
            breaker("ETH/USD")
        with self.assertRaises(ConnectionError):
            breaker("ETH/USD")
        self.assertEqual(breaker("ETH/USD"), 100.0)
        self.assertEqual(breaker("BTC/USD"), 100.0)
        with self.assertRaises(ConnectionError):
            breaker("ETH/USD")
        self.assertFalse(breaker.halted)

    def test_owner_reset_restores_calls(self):
        breaker = MarketDataCircuitBreaker(
            lambda symbol: (_ for _ in ()).throw(ConnectionError()),
            failure_threshold=1)
        with self.assertRaises(ConnectionError):
            breaker("BTC/USD")
        with self.assertRaises(MarketDataHalted):
            breaker("BTC/USD")
        breaker.reset_by_owner()
        self.assertFalse(breaker.halted)
        with self.assertRaises(ConnectionError):
            breaker("BTC/USD")

    def test_trip_persists_ledger_halt_across_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "desk.sqlite")
            desk = PersistentPaperDesk(path)
            def failing(symbol):
                raise ConnectionError("market-data outage")
            breaker = MarketDataCircuitBreaker(
                failing, failure_threshold=2, on_halt=desk.halt)
            with self.assertRaises(ConnectionError):
                breaker("BTC/USD")
            self.assertFalse(desk.snapshot().kill_switch)
            with self.assertRaises(ConnectionError):
                breaker("BTC/USD")
            self.assertTrue(breaker.halted)
            self.assertTrue(desk.halt_requested())
            self.assertTrue(PersistentPaperDesk(path).snapshot().kill_switch)
            breaker.reset_by_owner()
            self.assertFalse(breaker.halted)
            self.assertTrue(desk.snapshot().kill_switch)

    def test_failed_halt_callback_fails_closed(self):
        def failed_halt():
            raise OSError("ledger unavailable")
        breaker = MarketDataCircuitBreaker(
            lambda symbol: (_ for _ in ()).throw(ConnectionError()),
            failure_threshold=1, on_halt=failed_halt)
        with self.assertRaises(MarketDataHalted):
            breaker("BTC/USD")
        self.assertTrue(breaker.halted)

    def test_invalid_configuration(self):
        with self.assertRaises(ValueError):
            MarketDataCircuitBreaker(lambda s: 1, failure_threshold=0)

    def test_concurrent_calls_do_not_bypass_halt(self):
        calls = []
        def source(symbol):
            calls.append(symbol)
            raise ConnectionError()
        breaker = MarketDataCircuitBreaker(source, failure_threshold=1)
        errors = []
        def worker():
            try:
                breaker("BTC/USD")
            except (ConnectionError, MarketDataHalted) as exc:
                errors.append(type(exc))
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(errors), 8)


if __name__ == "__main__":
    unittest.main()
