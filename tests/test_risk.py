import unittest
from trading_desk.risk import check_proposed_risk


class RiskTests(unittest.TestCase):
    def test_accepts_five_dollars_at_500_equity(self):
        self.assertTrue(check_proposed_risk(500, 5, 0).approved)

    def test_rejects_more_than_one_percent(self):
        self.assertFalse(check_proposed_risk(500, 5.01, 0).approved)

    def test_rejects_daily_loss_limit(self):
        self.assertFalse(check_proposed_risk(500, 1, -15).approved)

    def test_rejects_nonpositive_equity(self):
        self.assertFalse(check_proposed_risk(0, 1, 0).approved)


if __name__ == '__main__':
    unittest.main()
