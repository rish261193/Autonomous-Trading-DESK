import sys, os, sqlite3, tempfile, time, threading
sys.path.insert(0, sys.argv[1])
from trading_desk.persistent_paper import PersistentPaperDesk
from trading_desk.pending_orders import PendingOrders
d=tempfile.mkdtemp(); p=os.path.join(d,"l.sqlite"); desk=PersistentPaperDesk(p); desk.mark("BTC/USD",100); po=PendingOrders(desk)
# performance
O=dict(strategy_id="s", symbol="BTC/USD", price=100, stop_price=99.99, quantity=0.01, strategy_authorized=True, market_data_fresh=True)
t=time.perf_counter(); n=200
for i in range(n):
    po.reserve(str(i), **O); po.fill(str(i), strategy_authorized=True, market_data_fresh=True, expected_strategy_id="s", expected_symbol="BTC/USD")
el=time.perf_counter()-t; print(f"PERF reserve+fill pairs: {n} in {el:.2f}s = {n/el:.0f}/s; positions={len(desk.snapshot().positions)}; db={os.path.getsize(p)} bytes")
t=time.perf_counter()
for i in range(200): desk.apply_stop_mark("BTC/USD", 100)
el=time.perf_counter()-t; print(f"PERF stop-mark evaluations with {len(desk.snapshot().positions)} open positions: {200/el:.0f}/s")
# kill switch under lock contention
blocker=sqlite3.connect(p, isolation_level=None); blocker.execute("BEGIN IMMEDIATE")
res={}
def h():
    t=time.perf_counter()
    try: desk.halt(); res["r"]="halted"
    except Exception as e: res["r"]=f"{type(e).__name__}: {e}"
    res["t"]=time.perf_counter()-t
th=threading.Thread(target=h); th.start(); time.sleep(0.5)
t1=time.perf_counter(); 
try: refused = po.reserve("during-halt", **O) is False
except Exception as e: refused = f"{type(e).__name__}"
print("reserve during contended halt -> refused:", refused, f"in {time.perf_counter()-t1:.2f}s; halt flag:", getattr(desk, "halt_requested", lambda: None)())
th.join(); blocker.rollback(); blocker.close()
print("KILL-SWITCH while another writer holds the lock:", res, "persisted kill_switch:", desk.snapshot().kill_switch)
