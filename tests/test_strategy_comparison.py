import unittest
from datetime import datetime, timedelta, timezone

from trading_desk.research import Bar, Costs
from trading_desk.strategy_comparison import compare_holdout, simulate


class StrategyComparisonTests(unittest.TestCase):
    def setUp(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.bars = [Bar(start + timedelta(hours=i), 100 + i * .2 + (i % 7 - 3) * 2)
                     for i in range(100)]

    def test_cash_baseline_is_flat(self):
        result = simulate(self.bars, strategy="cash", lookback=6)
        self.assertEqual(result.net_return_pct, 0)
        self.assertEqual(result.transactions, 0)

    def test_buy_hold_charges_costs(self):
        free = simulate(self.bars, strategy="buy_hold", lookback=6, costs=Costs(0, 0))
        costly = simulate(self.bars, strategy="buy_hold", lookback=6, costs=Costs(10, 5))
        self.assertLess(costly.net_return_pct, free.net_return_pct)
        self.assertEqual(costly.transactions, 2)

    def test_both_strategies_run(self):
        for name in ("momentum", "mean_reversion"):
            result = simulate(self.bars, strategy=name, lookback=6)
            self.assertGreaterEqual(result.transactions, 0)
            self.assertGreaterEqual(result.max_drawdown_pct, 0)

    def test_train_only_selection_and_baselines(self):
        report = compare_holdout(self.bars, lookbacks=(4, 6, 12))
        self.assertEqual(report["train_bars"], 70)
        self.assertEqual(report["holdout_bars"], 30)
        self.assertIn(report["selected_on_training"]["strategy"], ("momentum", "mean_reversion"))
        self.assertEqual(set(report["holdout_baselines"]), {"buy_hold", "cash"})

    def test_rejects_invalid_lookback(self):
        with self.assertRaises(ValueError):
            compare_holdout(self.bars, lookbacks=(0,))

    def test_rejects_invalid_costs(self):
        with self.assertRaises(ValueError):
            simulate(self.bars, strategy="momentum", lookback=6, costs=Costs(-1, 0))

    def test_rejects_insufficient_holdout(self):
        with self.assertRaises(ValueError):
            compare_holdout(self.bars[:10], lookbacks=(6,))


if __name__ == "__main__":
    unittest.main()
