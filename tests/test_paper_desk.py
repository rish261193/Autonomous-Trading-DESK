import unittest

from trading_desk.paper_desk import PaperDesk


class PaperDeskTests(unittest.TestCase):
    def setUp(self):
        self.desk = PaperDesk()
        self.desk.mark("BTC/USD", 100)
        self.order = dict(strategy_id="momentum-v1", symbol="BTC/USD",
                          price=100, stop_price=95, quantity=1,
                          strategy_authorized=True, market_data_fresh=True)

    def test_approved_entry_debits_cash_and_records_risk(self):
        self.assertTrue(self.desk.enter(**self.order))
        self.assertEqual(self.desk.cash_usd, 400)
        self.assertEqual(len(self.desk.positions), 1)
        self.assertEqual(self.desk.positions[0].risk_usd, 5)

    def test_combined_risk_limit_is_enforced(self):
        self.assertTrue(self.desk.enter(**self.order))
        self.assertFalse(self.desk.enter(**self.order))
        self.assertEqual(len(self.desk.positions), 1)
        self.assertEqual(self.desk.cash_usd, 400)

    def test_kill_switch_blocks_entries(self):
        self.desk.halt()
        self.assertFalse(self.desk.enter(**self.order))
        self.assertEqual(self.desk.cash_usd, 500)

    def test_unauthorized_or_stale_rejected(self):
        for change in ({"strategy_authorized": False},
                       {"market_data_fresh": False}):
            with self.subTest(change=change):
                self.assertFalse(self.desk.enter(**(self.order | change)))
        self.assertEqual(len(self.desk.positions), 0)

    def test_daily_loss_cap_rejects(self):
        self.desk.daily_realized_pnl_usd = -15
        self.assertFalse(self.desk.enter(**self.order))

    def test_invalid_stop_or_nonfinite_rejected(self):
        for change in ({"stop_price": 100}, {"stop_price": 101},
                       {"price": float("nan")}, {"quantity": float("inf")},
                       {"quantity": -1}):
            with self.subTest(change=change):
                self.assertFalse(self.desk.enter(**(self.order | change)))
        self.assertEqual(self.desk.cash_usd, 500)

    def test_no_short_or_unknown_symbol(self):
        self.assertFalse(self.desk.enter(**(self.order | {"symbol": "SOL/USD"})))

    def test_missing_or_mismatched_mark_rejected(self):
        self.desk.marks.clear()
        self.assertFalse(self.desk.enter(**self.order))
        self.desk.mark("BTC/USD", 101)
        self.assertFalse(self.desk.enter(**self.order))
        self.assertEqual(self.desk.cash_usd, 500)

    def test_mark_to_market_daily_loss(self):
        self.assertTrue(self.desk.enter(**self.order))
        self.desk.mark("BTC/USD", 85)
        self.assertFalse(self.desk.enter(**(self.order | {"price": 85, "stop_price": 80})))

    def test_close_realizes_pnl_and_frees_cash(self):
        self.assertTrue(self.desk.enter(**self.order))
        self.desk.mark("BTC/USD", 102)
        self.assertEqual(self.desk.close(0, 102), 2)
        self.assertEqual(self.desk.cash_usd, 502)
        self.assertEqual(self.desk.daily_realized_pnl_usd, 2)
        self.assertEqual(len(self.desk.positions), 0)

    def test_midnight_reset_keeps_position(self):
        self.assertTrue(self.desk.enter(**self.order))
        self.desk.mark("BTC/USD", 102)
        self.desk.reset_daily_baseline()
        self.assertEqual(len(self.desk.positions), 1)
        self.assertEqual(self.desk.day_start_equity_usd, 502)

    def test_cash_limit_blocks_overspending(self):
        self.assertFalse(self.desk.enter(**(self.order | {
            "price": 100, "stop_price": 99.9, "quantity": 6
        })))
        self.assertEqual(self.desk.cash_usd, 500)


if __name__ == "__main__":
    unittest.main()
