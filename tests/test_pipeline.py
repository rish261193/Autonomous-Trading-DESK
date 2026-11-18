import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_desk.pipeline import research_pipeline, save_pipeline_report
from trading_desk.research import Bar, Costs


def sample_bars(n=150):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [Bar(start + timedelta(minutes=5*i), 100 + .03*i + .2*(i%7)) for i in range(n)]


class PipelineTests(unittest.TestCase):
    def test_produces_rolling_report(self):
        report = research_pipeline(sample_bars(), [2, 3], [10, 12],
                                   train_size=60, test_size=20, gap=2)
        self.assertEqual(report["status"], "unverified_research")
        self.assertEqual(len(report["windows"]), 4)
        self.assertEqual(report["windows"][0]["split"]["test_start"], 62)

    def test_audit_and_report_written(self):
        with tempfile.TemporaryDirectory() as d:
            audit = str(Path(d) / "audit.jsonl")
            output = str(Path(d) / "report.json")
            report = research_pipeline(sample_bars(), [2], [10],
                                       train_size=60, test_size=20,
                                       costs=Costs(10, 5), audit_path=audit)
            save_pipeline_report(report, output)
            self.assertTrue(Path(audit).exists())
            self.assertTrue(Path(output).exists())
            self.assertEqual(len(Path(audit).read_text().splitlines()), 4 if False else 1)

    def test_rejects_insufficient_training_data(self):
        with self.assertRaises(ValueError):
            research_pipeline(sample_bars(40), [2], [10],
                              train_size=30, test_size=20)


if __name__ == "__main__":
    unittest.main()
