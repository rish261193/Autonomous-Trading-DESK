import unittest
from datetime import datetime, timedelta, timezone

from trading_desk.intelligence import ResearchSignal, evaluate_signals


class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.allowed = frozenset({"technical", "quant"})
        self.signals = [
            ResearchSignal("technical", "BTC/USD", "buy", .78, "trend", self.now),
            ResearchSignal("quant", "BTC/USD", "buy", .71, "momentum", self.now),
        ]

    def evaluate(self, signals):
        return evaluate_signals(signals, now=self.now, allowed_analysts=self.allowed)

    def test_consensus_is_research_only_and_deterministic(self):
        result = self.evaluate(self.signals)
        self.assertEqual(result.status, "research_only")
        self.assertEqual(result.confidence, .71)
        self.assertEqual(result.evidence_sha256,
                         self.evaluate(list(reversed(self.signals))).evidence_sha256)

    def test_rejects_conflict(self):
        self.assertIsNone(self.evaluate([self.signals[0],
                           ResearchSignal("quant", "BTC/USD", "sell", .8, "risk", self.now)]))

    def test_rejects_duplicate_or_unapproved_analyst(self):
        self.assertIsNone(self.evaluate([self.signals[0], self.signals[0]]))
        self.assertIsNone(self.evaluate([self.signals[0],
                           ResearchSignal("other", "BTC/USD", "buy", .8, "x", self.now)]))

    def test_rejects_stale_and_future(self):
        for delta in (-120, 10):
            changed = ResearchSignal("quant", "BTC/USD", "buy", .8, "x",
                                     self.now + timedelta(seconds=delta))
            self.assertIsNone(self.evaluate([self.signals[0], changed]))

    def test_rejects_unsupported_market(self):
        changed = ResearchSignal("quant", "DOGE/USD", "buy", .8, "x", self.now)
        self.assertIsNone(self.evaluate([self.signals[0], changed]))

    def test_rejects_low_confidence(self):
        changed = ResearchSignal("quant", "BTC/USD", "buy", .5, "x", self.now)
        self.assertIsNone(self.evaluate([self.signals[0], changed]))


if __name__ == "__main__":
    unittest.main()
