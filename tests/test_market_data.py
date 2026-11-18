import json
import tempfile
import unittest
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from trading_desk.market_data import fetch_kraken_hourly, parse_kraken_ohlc, save_dataset
from trading_desk.research import load_csv


def sample():
    candles = []
    for i in range(5):
        t = 1767225600 + i * 3600
        candles.append([t, "100", "110", "90", str(100 + i), "101", "2", 3])
    return {"error": [], "result": {"XXBTZUSD": candles, "last": 123}}


class MarketDataTests(unittest.TestCase):
    def test_excludes_last_incomplete_candle(self):
        bars, meta = parse_kraken_ohlc(sample(), symbol="BTC/USD")
        self.assertEqual(len(bars), 4)
        self.assertEqual(bars[-1].close, 103)
        self.assertEqual(meta["excluded_incomplete_candles"], 1)
        self.assertEqual(meta["missing_hourly_intervals"], 0)

    def test_rejects_api_error(self):
        p = sample()
        p["error"] = ["EQuery:Invalid asset pair"]
        with self.assertRaises(ValueError):
            parse_kraken_ohlc(p, symbol="BTC/USD")

    def test_detects_gap(self):
        p = sample()
        p["result"]["XXBTZUSD"][2][0] += 3600
        p["result"]["XXBTZUSD"].pop(3)
        bars, meta = parse_kraken_ohlc(p, symbol="BTC/USD")
        self.assertEqual(meta["missing_hourly_intervals"], 1)

    def test_rejects_duplicate_timestamp(self):
        p = sample()
        p["result"]["XXBTZUSD"][1][0] = p["result"]["XXBTZUSD"][0][0]
        with self.assertRaises(ValueError):
            parse_kraken_ohlc(p, symbol="BTC/USD")

    def test_rejects_bad_price(self):
        p = sample()
        p["result"]["XXBTZUSD"][0][4] = "NaN"
        with self.assertRaises(ValueError):
            parse_kraken_ohlc(p, symbol="BTC/USD")

    def test_save_manifest_matches_csv(self):
        bars, meta = parse_kraken_ohlc(sample(), symbol="BTC/USD")
        with tempfile.TemporaryDirectory() as folder:
            prefix = str(Path(folder) / "btc")
            manifest = save_dataset(bars, meta, output_prefix=prefix)
            self.assertEqual(manifest["data_sha256"],
                             sha256(Path(prefix + ".csv").read_bytes()).hexdigest())
            self.assertEqual(len(load_csv(prefix + ".csv")), 4)

    def test_rejects_unsupported_symbol(self):
        with self.assertRaises(ValueError):
            fetch_kraken_hourly("DOGE/USD")


if __name__ == "__main__":
    unittest.main()
