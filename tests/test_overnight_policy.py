"""Regression tests for approved 24/7 holding policy."""
import unittest
from datetime import datetime, timedelta, timezone
from trading_desk.research import Bar, Costs, backtest
from trading_desk.signals import SignalSpec
from trading_desk.simulator import simulate

class OvernightPolicyTests(unittest.TestCase):
    def setUp(self):
        start = datetime(2026, 1, 1, 23, 30, tzinfo=timezone.utc)
        self.bars = [Bar(start + timedelta(minutes=5*i), 100 + i)
                     for i in range(24)]

    def test_sma_no_forced_midnight_exit(self):
        result = backtest(self.bars, 2, 5, Costs(0, 0))
        # Rising prices stay long through midnight, with one buy and one
        # final dataset liquidation. No artificial midnight sell/rebuy.
        self.assertEqual(result.trades, 2)

    def test_momentum_no_forced_midnight_exit(self):
        result = simulate(self.bars, SignalSpec("momentum", 3), Costs(0, 0))
        self.assertEqual(result.trades, 2)

    def test_midnight_does_not_reset_position(self):
        # The research baseline has no daily loss gateway; midnight must
        # not generate a position change on its own.
        result = simulate(self.bars, SignalSpec("breakout", 3), Costs(0, 0))
        self.assertEqual(result.trades, 2)

if __name__ == "__main__":
    unittest.main()
