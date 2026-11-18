import sys, os
sys.path.insert(0, sys.argv[1])
from trading_desk.persistent_paper import PersistentPaperDesk
from trading_desk.pending_orders import PendingOrders
d = PersistentPaperDesk(sys.argv[2]); d.mark("BTC/USD", 100); po = PendingOrders(d)
O = dict(strategy_id="s1", symbol="BTC/USD", price=100, stop_price=98, quantity=1, strategy_authorized=True, market_data_fresh=True)
for oid in ("a", "b"):
    po.reserve(oid, **(O | {"quantity": 1})) and po.fill(oid, strategy_authorized=True, market_data_fresh=True, expected_strategy_id="s1", expected_symbol="BTC/USD")
po.reserve("c", **(O|{"quantity":0.5}))
d.mark("BTC/USD", 101); d.close(0, 101); po.cancel("c"); d.halt()
print("legacy positions", len(d.snapshot().positions), "cash", d.snapshot().cash_usd)
