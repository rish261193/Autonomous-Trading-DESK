import tempfile
import unittest
from pathlib import Path
from hashlib import sha256

from trading_desk.ccxt_market_data import fetch_public_hourly, normalize_completed_ohlcv, save_ohlcv

HOUR = 3_600_000


def candles():
    return [[HOUR, 100, 110, 90, 105, 2],
            [2 * HOUR, 105, 112, 100, 108, 3],
            [3 * HOUR, 108, 115, 107, 112, 4]]


class FakeExchange:
    id = "kraken"
    has = {"fetchOHLCV": True}
    def fetch_ohlcv(self, symbol, timeframe):
        assert symbol == "BTC/USD" and timeframe == "1h"
        return candles()


class TestCCXTAdapter(unittest.TestCase):
    def test_drops_unfinished_last_candle(self):
        rows, meta = normalize_completed_ohlcv(candles(), symbol="BTC/USD", now_ms=3 * HOUR + 1000)
        self.assertEqual(len(rows), 2)
        self.assertEqual(meta["excluded_unfinished"], 1)

    def test_retains_full_ohlcv(self):
        rows, _ = normalize_completed_ohlcv(candles(), symbol="ETH/USD", now_ms=4 * HOUR)
        self.assertEqual(rows[0], (HOUR, 100., 110., 90., 105., 2.))

    def test_gap_rejected(self):
        c = candles()
        c.pop(1)
        with self.assertRaisesRegex(ValueError, "missing"):
            normalize_completed_ohlcv(c, symbol="BTC/USD", now_ms=5 * HOUR)

    def test_duplicate_rejected(self):
        c = candles()
        c[1][0] = c[0][0]
        with self.assertRaises(ValueError):
            normalize_completed_ohlcv(c, symbol="BTC/USD", now_ms=5 * HOUR)

    def test_bad_ohlc_rejected(self):
        c = candles()
        c[0][2] = 99
        with self.assertRaises(ValueError):
            normalize_completed_ohlcv(c, symbol="BTC/USD", now_ms=5 * HOUR)

    def test_nonfinite_rejected(self):
        c = candles()
        c[0][4] = "NaN"
        with self.assertRaises(ValueError):
            normalize_completed_ohlcv(c, symbol="BTC/USD", now_ms=5 * HOUR)

    def test_bad_symbol_rejected_before_exchange(self):
        with self.assertRaises(ValueError):
            fetch_public_hourly("DOGE/USD", exchange=FakeExchange())

    def test_wrong_exchange_rejected(self):
        e = FakeExchange()
        e.id = "binance"
        with self.assertRaises(ValueError):
            fetch_public_hourly("BTC/USD", exchange=e)

    def test_injected_exchange_no_credentials(self):
        rows, meta = fetch_public_hourly("BTC/USD", exchange=FakeExchange(), now_ms=4 * HOUR)
        self.assertEqual(len(rows), 3)
        self.assertEqual(meta["exchange"], "kraken")

    def test_persistence_digest_and_no_overwrite(self):
        rows, meta = normalize_completed_ohlcv(candles(), symbol="BTC/USD", now_ms=4 * HOUR)
        with tempfile.TemporaryDirectory() as d:
            prefix = str(Path(d) / "btc")
            manifest = save_ohlcv(rows, meta, output_prefix=prefix)
            self.assertEqual(manifest["data_sha256"], sha256(Path(prefix + ".csv").read_bytes()).hexdigest())
            self.assertIn("volume", Path(prefix + ".csv").read_text())
            with self.assertRaises(FileExistsError):
                save_ohlcv(rows, meta, output_prefix=prefix)


if __name__ == "__main__":
    unittest.main()
