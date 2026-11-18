import unittest
from datetime import datetime, timedelta, timezone
from trading_desk.research import Bar, Costs
from trading_desk.signals import SignalSpec, signal_at
from trading_desk.simulator import simulate, screen

def sample(n=100):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [Bar(start + timedelta(minutes=i*5), 100 + .1*i + (i % 9)*.03)
            for i in range(n)]

class SignalTests(unittest.TestCase):
    def test_future_price_does_not_change_signal(self):
        prices = [100 + i for i in range(30)]
        original = signal_at(prices, 20, SignalSpec("momentum", 5))
        prices[20:] = [1e8] * 10
        self.assertEqual(original, signal_at(prices, 20, SignalSpec("momentum", 5)))

    def test_all_families(self):
        prices = [100, 101, 102, 103, 104, 105]
        self.assertTrue(signal_at(prices, 6, SignalSpec("momentum", 3)))
        self.assertTrue(signal_at(prices, 6, SignalSpec("breakout", 3)))
        self.assertFalse(signal_at(prices, 6, SignalSpec("mean_reversion", 3)))

    def test_invalid_family(self):
        with self.assertRaises(ValueError):
            signal_at([100]*20, 10, SignalSpec("unknown", 3))

class SimulatorTests(unittest.TestCase):
    def test_costs_reduce_equity(self):
        bars = sample()
        spec = SignalSpec("momentum", 5)
        free = simulate(bars, spec, Costs(0, 0))
        costly = simulate(bars, spec, Costs(10, 5))
        self.assertLess(costly.ending_equity, free.ending_equity)

    def test_screen_multiple_families(self):
        results = screen(sample(), [SignalSpec("momentum", 5),
                                    SignalSpec("mean_reversion", 5),
                                    SignalSpec("breakout", 5)])
        self.assertEqual(len(results), 3)
        self.assertEqual([r.net_return_pct for r in results],
                         sorted([r.net_return_pct for r in results], reverse=True))

    def test_reject_invalid_cost(self):
        with self.assertRaises(ValueError):
            simulate(sample(), SignalSpec("momentum", 5), Costs(-1, 0))

if __name__ == "__main__":
    unittest.main()
