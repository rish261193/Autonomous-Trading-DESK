import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from trading_desk.research import Bar, Costs, backtest, grid_search, walk_forward, load_csv

def bars(n=150, daily=False):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    step = timedelta(days=1) if daily else timedelta(minutes=5)
    return [Bar(start + i*step, 100 + i*.1) for i in range(n)]

class ResearchTests(unittest.TestCase):
    def test_no_future_signal(self):
        original = bars()
        modified = list(original)
        modified[-1] = Bar(modified[-1].timestamp, 999)
        # Earlier portion must be unaffected by the last observation.
        self.assertEqual(backtest(original[:-1], 3, 12), backtest(modified[:-1], 3, 12))

    def test_fees_reduce_returns(self):
        a = backtest(bars(), 3, 12, Costs(0, 0))
        b = backtest(bars(), 3, 12, Costs(20, 10))
        self.assertLess(b.ending_equity, a.ending_equity)

    def test_end_flat(self):
        r = backtest(bars(), 3, 12)
        self.assertGreater(r.trades, 0)
        self.assertGreater(r.ending_equity, 0)

    def test_grid_sorted(self):
        r = grid_search(bars(), [2, 3], [12, 14])
        self.assertEqual(len(r), 4)
        self.assertEqual([x.net_return_pct for x in r],
                         sorted([x.net_return_pct for x in r], reverse=True))

    def test_holdout_split(self):
        r = walk_forward(bars(), [2, 3], [12, 14])
        self.assertEqual(r["train_bars"], 105)
        self.assertEqual(r["holdout_bars"], 45)

    def test_reject_unsorted(self):
        with self.assertRaises(ValueError):
            backtest(list(reversed(bars())), 3, 12)

    def test_reject_nonfinite_and_excessive_costs(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    backtest(bars(), 3, 12, Costs(value, 0))
                with self.assertRaises(ValueError):
                    backtest(bars(), 3, 12, initial_equity=value)
        for fees in (-1, 10000, 11000):
            with self.subTest(fees=fees):
                with self.assertRaises(ValueError):
                    backtest(bars(), 3, 12, Costs(fees, 0))

    def test_reject_noninteger_windows(self):
        for fast, slow in ((True, 12), (3.0, 12), (3, False), (3, 12.0)):
            with self.subTest(fast=fast, slow=slow):
                with self.assertRaises(ValueError):
                    backtest(bars(), fast, slow)

    def test_csv_requires_timezone(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bars.csv"
            p.write_text("timestamp,close\n2026-01-01T00:00:00,100\n2026-01-01T00:05:00,101\n2026-01-01T00:10:00,102\n")
            with self.assertRaises(ValueError):
                load_csv(str(p))

if __name__ == "__main__":
    unittest.main()
