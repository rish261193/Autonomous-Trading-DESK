import json
import tempfile
import unittest
from pathlib import Path
from trading_desk.metrics import evaluate_equity
from trading_desk.validation import rolling_splits
from trading_desk.audit import fingerprint, make_experiment_record, append_jsonl

class PerformanceTests(unittest.TestCase):
    def test_flat_curve(self):
        r = evaluate_equity([100, 100, 100])
        self.assertEqual(r.net_return_pct, 0)
        self.assertEqual(r.max_drawdown_pct, 0)
        self.assertIsNone(r.sharpe_per_period)

    def test_drawdown(self):
        r = evaluate_equity([100, 120, 90, 110])
        self.assertAlmostEqual(r.max_drawdown_pct, 25)

    def test_invalid_curve(self):
        with self.assertRaises(ValueError):
            evaluate_equity([100, 0])

class ValidationTests(unittest.TestCase):
    def test_rolling_gap(self):
        splits = rolling_splits(100, 40, 10, gap=3)
        self.assertEqual(len(splits), 5)
        self.assertEqual((splits[0].train_end, splits[0].test_start), (40, 43))
        self.assertEqual((splits[-1].test_start, splits[-1].test_end), (83, 93))

    def test_not_enough_data(self):
        with self.assertRaises(ValueError):
            rolling_splits(20, 20, 5)

class AuditTests(unittest.TestCase):
    def test_append_and_fingerprint(self):
        digest = fingerprint(b"example price data")
        record = make_experiment_record("sma", {"fast": 3}, digest, {"net": -1.2})
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "audit.jsonl")
            append_jsonl(path, record)
            append_jsonl(path, record)
            lines = Path(path).read_text().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["status"], "unverified_research")

if __name__ == "__main__":
    unittest.main()
