import unittest
from datetime import datetime, timedelta, timezone
from trading_desk.tools import build_research_registry

class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = build_research_registry()
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        from trading_desk.research import Bar
        self.bars = [Bar(start + timedelta(minutes=5*i), 100 + i*.1) for i in range(60)]

    def test_role_catalog(self):
        self.assertEqual(len(self.registry.catalog("quant_analyst")), 3)
        self.assertEqual(self.registry.catalog("whatsapp_crm"), [])

    def test_candidates(self):
        result = self.registry.invoke("research.sma_candidates", "technical_analyst",
                                      {"fast_windows": [2, 3], "slow_windows": [10]})
        self.assertTrue(result.success)
        self.assertEqual(len(result.output), 2)

    def test_backtest(self):
        result = self.registry.invoke("research.sma_backtest", "quant_analyst",
                                      {"bars": self.bars, "fast": 3, "slow": 12})
        self.assertTrue(result.success)
        self.assertIn("net_return_pct", result.output)

    def test_reject_crm(self):
        result = self.registry.invoke("research.sma_grid", "whatsapp_crm",
                                      {"bars": self.bars, "fast_windows": [3], "slow_windows": [12]})
        self.assertFalse(result.success)

    def test_reject_unknown(self):
        self.assertFalse(self.registry.invoke("broker.place_order", "quant_analyst", {}).success)

    def test_reject_excessive_grid(self):
        result = self.registry.invoke("research.sma_candidates", "quant_analyst",
                                      {"fast_windows": list(range(101)), "slow_windows": list(range(101))})
        self.assertFalse(result.success)

    def test_reject_bad_bars(self):
        result = self.registry.invoke("research.sma_backtest", "quant_analyst",
                                      {"bars": ["invalid"], "fast": 3, "slow": 12})
        self.assertFalse(result.success)

if __name__ == "__main__":
    unittest.main()
