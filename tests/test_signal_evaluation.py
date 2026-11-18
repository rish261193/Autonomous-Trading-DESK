import unittest
from datetime import datetime, timedelta, timezone

from trading_desk.intelligence import ResearchDecision
from trading_desk.research import Bar, Costs
from trading_desk.signal_evaluation import evaluate_history


class SignalEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.t = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.bars = [Bar(self.t + timedelta(hours=i), p)
                     for i, p in enumerate((100, 110, 105, 120, 115))]
        self.buy = ResearchDecision("BTC/USD", "buy", .8, 2, "evidence")
        self.hold = ResearchDecision("BTC/USD", "hold", .8, 2, "evidence")

    def test_long_net_costs_and_baseline(self):
        r = evaluate_history(self.bars, {self.t: self.buy}, costs=Costs(10, 5))
        self.assertEqual(r["evaluated"], 1)
        self.assertEqual(r["long_signals"], 1)
        self.assertAlmostEqual(r["mean_baseline_return_pct"], 10)
        self.assertLess(r["mean_long_net_return_pct"], 10)
        self.assertGreater(r["mean_long_net_return_pct"], 9)

    def test_hold_is_not_short(self):
        r = evaluate_history(self.bars, {self.t: self.hold})
        self.assertEqual(r["abstentions"], 1)
        self.assertEqual(r["mean_signal_net_return_pct"], 0)
        self.assertIsNone(r["long_win_rate"])

    def test_last_bar_is_not_scored(self):
        r = evaluate_history(self.bars, {self.bars[-1].timestamp: self.buy})
        self.assertEqual(r["evaluated"], 0)

    def test_evidence_is_order_invariant(self):
        d = {self.t: self.buy, self.bars[1].timestamp: self.hold}
        a = evaluate_history(self.bars, d)
        b = evaluate_history(self.bars, dict(reversed(list(d.items()))))
        self.assertEqual(a["evidence_sha256"], b["evidence_sha256"])

    def test_unknown_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_history(self.bars, {self.t - timedelta(hours=1): self.buy})

    def test_invalid_horizon_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_history(self.bars, {}, horizon_bars=0)

    def test_non_research_decision_rejected(self):
        invalid = ResearchDecision("BTC/USD", "buy", .8, 2, "x", status="approved")
        with self.assertRaises(ValueError):
            evaluate_history(self.bars, {self.t: invalid})


if __name__ == "__main__":
    unittest.main()
