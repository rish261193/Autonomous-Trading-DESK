import unittest
from dataclasses import replace

from trading_desk.gateway import (
    GatewayState, OrderIntent, authorize,
)
from trading_desk.strategies import sma_hypotheses, validate_strategy, StrategySpec


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.state = GatewayState(500, 500, 0, 0, False, True, True)
        self.intent = OrderIntent("sma_long-v1-fast3-slow20", "BTC/USD", "buy", 100, 4)

    def test_approved_baseline(self):
        self.assertTrue(authorize(self.intent, self.state).allowed)

    def test_kill_switch(self):
        self.assertFalse(authorize(self.intent, replace(self.state, kill_switch=True)).allowed)

    def test_unauthorized_strategy(self):
        self.assertFalse(authorize(self.intent, replace(self.state, strategy_authorized=False)).allowed)

    def test_stale_data(self):
        self.assertFalse(authorize(self.intent, replace(self.state, market_data_fresh=False)).allowed)

    def test_daily_loss(self):
        self.assertFalse(authorize(self.intent, replace(self.state, daily_realized_pnl_usd=-15)).allowed)

    def test_combined_open_risk(self):
        self.assertFalse(authorize(self.intent, replace(self.state, open_risk_usd=2)).allowed)

    def test_no_short(self):
        self.assertFalse(authorize(replace(self.intent, side="sell"), self.state).allowed)

    def test_reject_nonfinite(self):
        self.assertFalse(authorize(replace(self.intent, notional_usd=float("nan")), self.state).allowed)


class StrategyTests(unittest.TestCase):
    def test_generated_hypotheses(self):
        candidates = sma_hypotheses([3, 5], [10, 20])
        self.assertEqual(len(candidates), 4)
        for candidate in candidates:
            validate_strategy(candidate)

    def test_invalid_strategy(self):
        with self.assertRaises(ValueError):
            validate_strategy(StrategySpec("sma_long", (("fast", 20), ("slow", 3))))


if __name__ == "__main__":
    unittest.main()
