import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_desk.experiment_runner import load_decisions, run_experiment


class ExperimentRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.prices = Path(self.temp.name) / "prices.csv"
        self.signals = Path(self.temp.name) / "signals.csv"
        self.start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with self.prices.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "close"])
            for i, close in enumerate((100, 110, 105, 115)):
                writer.writerow([(self.start + timedelta(hours=i)).isoformat(), close])
        self._signals([(self.start.isoformat(), "BTC/USD", "buy", ".75", "2", "a" * 64)])

    def _signals(self, rows):
        with self.signals.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "symbol", "direction", "confidence",
                             "analyst_count", "evidence_sha256"])
            writer.writerows(rows)

    def test_offline_report(self):
        result = run_experiment(prices_csv=str(self.prices), signals_csv=str(self.signals),
                                symbol="BTC/USD")
        self.assertEqual(result["evaluated"], 1)
        self.assertEqual(result["long_signals"], 1)
        self.assertEqual(result["price_bars"], 4)
        self.assertIn("cannot establish", result["provenance_warning"])

    def test_rejects_duplicate_signal_timestamp(self):
        row = (self.start.isoformat(), "BTC/USD", "buy", ".75", "2", "a" * 64)
        self._signals([row, row])
        with self.assertRaises(ValueError):
            load_decisions(str(self.signals), expected_symbol="BTC/USD")

    def test_rejects_wrong_symbol(self):
        with self.assertRaises(ValueError):
            run_experiment(prices_csv=str(self.prices), signals_csv=str(self.signals),
                           symbol="ETH/USD")

    def test_rejects_missing_columns(self):
        self.signals.write_text("timestamp,direction\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_decisions(str(self.signals), expected_symbol="BTC/USD")

    def test_rejects_future_signal_without_bar(self):
        self._signals([((self.start - timedelta(hours=1)).isoformat(),
                        "BTC/USD", "buy", ".75", "2", "a" * 64)])
        with self.assertRaises(ValueError):
            run_experiment(prices_csv=str(self.prices), signals_csv=str(self.signals),
                           symbol="BTC/USD")


if __name__ == "__main__":
    unittest.main()
