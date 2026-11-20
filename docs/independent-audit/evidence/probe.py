import sys, json, sqlite3, tempfile, os
from datetime import datetime, timedelta, timezone
sys.path.insert(0, sys.argv[1])
from trading_desk.persistent_paper import PersistentPaperDesk
from trading_desk.pending_orders import PendingOrders
from trading_desk.paper_controller import GuardedPaperController, PriceObservation
from trading_desk.paper_stops import process_stop_observation
from trading_desk.agent_contracts import AgentEvent, AgentResponse, EventType, Role
from trading_desk.orchestrator import Orchestrator

def fresh():
    d = tempfile.mkdtemp(); p = os.path.join(d, "l.sqlite")
    desk = PersistentPaperDesk(p); return p, desk
NOW = datetime.now(timezone.utc)
O = dict(strategy_id="approved-v1", symbol="BTC/USD", price=100, stop_price=95, quantity=1, strategy_authorized=True, market_data_fresh=True)
def ok(name, cond, detail=""): print(("DEFECT " if cond else "ok     ")+name, detail)

# P1 bypass controller allowlist
p, desk = fresh(); desk.mark("BTC/USD", 100); po = PendingOrders(desk)
r = po.reserve("x", **(O|{"strategy_id":"rogue-unapproved"})); f = po.fill("x", strategy_authorized=True, market_data_fresh=True, expected_strategy_id="rogue-unapproved", expected_symbol="BTC/USD")
ok("P1 unapproved strategy fills via PendingOrders directly", r and f)

# P2 hallucinated price accepted by controller (self-attested timestamp)
p, desk = fresh(); c = GuardedPaperController(desk, frozenset({"approved-v1"}))
ok("P2 controller accepts absurd price 1e9 with self-supplied timestamp", c.observe(PriceObservation("BTC/USD", 1e9, NOW), now=NOW))

# P3 fabricated realized P&L via public mark+close, survives restart reconcile
p, desk = fresh(); desk.mark("BTC/USD", 100); po=PendingOrders(desk); po.reserve("a", **O); po.fill("a", strategy_authorized=True, market_data_fresh=True, expected_strategy_id="approved-v1", expected_symbol="BTC/USD")
desk.mark("BTC/USD", 1_000_000); pnl = desk.close(0, 1_000_000); eq = PersistentPaperDesk(p).reconcile()
ok("P3 fabricated mark+close realizes P&L and passes restart reconcile", pnl > 900000, f"pnl={pnl} equity_after_restart={eq}")

# P4 mark below stop via observe does not trigger stop; later stop check misses it
p, desk = fresh(); c = GuardedPaperController(desk, frozenset({"approved-v1"}))
ob = PriceObservation("BTC/USD", 100, NOW); c.reserve("e", strategy_id="approved-v1", symbol="BTC/USD", price=100, stop_price=95, quantity=1, observation=ob, now=NOW); c.fill("e", strategy_id="approved-v1", observation=ob, now=NOW)
c.observe(PriceObservation("BTC/USD", 80, NOW), now=NOW)
s = desk.snapshot(); r = process_stop_observation(c, PriceObservation("BTC/USD", 96, NOW), now=NOW)
ok("P4 price observed at 80 (< stop 95) via observe() leaves position open; next stop check at 96 does nothing", len(desk.snapshot().positions)==1 and r.triggered==0, f"positions={len(s.positions)}")

# P5 gap: BTC+ETH simultaneous gap, loss vs 3% threshold; kill switch auto?
p, desk = fresh(); desk.mark("BTC/USD", 100); desk.mark("ETH/USD", 100); po=PendingOrders(desk)
po.reserve("b", **(O|{"stop_price":99, "quantity":2.5})); po.fill("b", strategy_authorized=True, market_data_fresh=True, expected_strategy_id="approved-v1", expected_symbol="BTC/USD")
po.reserve("e", **(O|{"symbol":"ETH/USD","stop_price":99, "quantity":2.4})); fe=po.fill("e", strategy_authorized=True, market_data_fresh=True, expected_strategy_id="approved-v1", expected_symbol="ETH/USD")
desk.apply_stop_mark("BTC/USD", 93); desk.apply_stop_mark("ETH/USD", 92)
s = desk.snapshot(); loss = 500 - s.equity()
ok("P5 simultaneous gap loss exceeds 3% daily threshold despite 1% planned risk", loss > 15, f"filled_eth={fe} loss=${loss:.2f} ({loss/5:.2f}% of 500) kill_switch={s.kill_switch}")

# P6 clock: caller rolls to 2099 -> baseline reset, subsequent reserve raises
p, desk = fresh(); desk.mark("BTC/USD", 100); po=PendingOrders(desk)
try:
    rolled = desk.roll_utc_day(now=datetime(2099,1,1,tzinfo=timezone.utc))
except ValueError as e:
    rolled = False; print("        P6 roll rejected:", e)
try: res = f"returned {po.reserve('z', **O)}"
except ValueError as e: res=f"raised {e}"
ok("P6 arbitrary future clock accepted by roll_utc_day; desk then refuses all orders until 2099", rolled and res.startswith("raised"), res)

# P7 ledger tamper: cash edit, day_start edit, event deletion undetected
p, desk = fresh(); desk.mark("BTC/USD", 100)
with sqlite3.connect(p) as db:
    pl = json.loads(db.execute("SELECT payload FROM state").fetchone()[0]); pl["cash_usd"]=1_000_000; pl["day_start_equity_usd"]=1_000_000
    db.execute("UPDATE state SET payload=?", (json.dumps(pl),)); db.execute("DELETE FROM events")
try: eq = PersistentPaperDesk(p).reconcile(); ok("P7 tampered cash/baseline + deleted event log pass restart reconcile", True, f"equity={eq}")
except ValueError as e: ok("P7 tampered cash/baseline + deleted event log detected at restart", False, str(e))

# P8 exact-price fill liveness
p, desk = fresh(); c = GuardedPaperController(desk, frozenset({"approved-v1"}))
ob = PriceObservation("BTC/USD", 100, NOW); c.reserve("e", strategy_id="approved-v1", symbol="BTC/USD", price=100, stop_price=95, quantity=1, observation=ob, now=NOW)
ob2 = PriceObservation("BTC/USD", 100.01, NOW); c.observe(ob2, now=NOW)
f = c.fill("e", strategy_id="approved-v1", observation=ob2, now=NOW)
r2 = c.reserve("e2", strategy_id="approved-v1", symbol="BTC/USD", price=100.01, stop_price=95.01, quantity=1, observation=ob2, now=NOW)
ok("P8 one-cent move makes reservation unfillable; its risk stays locked and blocks new orders", not f and not r2)

# P9 index-based close closes wrong position after a shift
p, desk = fresh(); desk.mark("BTC/USD", 100); po=PendingOrders(desk)
for oid, stop, q in (("A",98,1.0),("B",96,0.5),("C",90,0.1)):
    po.reserve(oid, **(O|{"stop_price":stop,"quantity":q})); po.fill(oid, strategy_authorized=True, market_data_fresh=True, expected_strategy_id="approved-v1", expected_symbol="BTC/USD")
before = [(x.stop_price) for x in desk.snapshot().positions]
desk.apply_stop_mark("BTC/USD", 97.5)   # stops A
desk.close_position("B", 97.5) if hasattr(desk, "close_position") else desk.close(1, 97.5)  # caller intended B (index 1 in its earlier snapshot)
after = [(x.stop_price) for x in desk.snapshot().positions]
ok("P9 close after concurrent stop closes the wrong position", after != [90], f"before={before} after={after} (intended to close stop=96)")

# P10 attribution / timestamps
s = desk.snapshot()
with sqlite3.connect(p) as db: cols=[r[1] for r in db.execute("PRAGMA table_info(events)")]
ok("P10 positions carry no strategy_id/order_id", not getattr(s.positions[0], "strategy_id", ""), str(s.positions[0]))
ok("P11 event log has no timestamp column", not any("time" in c or "_at" in c for c in cols), str(cols))

# P12 orchestrator producer spoofing
router = Orchestrator(); seen=[]
def bull(ev): return AgentResponse(Role.BULL_AGENT, ev.event_id, "x", proposed_events=(AgentEvent(EventType.STRATEGY_AUTHORIZED, Role.PORTFOLIO_MANAGER, {"strategy_id":"rogue"}),))
def pm(ev): seen.append(ev.payload); return AgentResponse(Role.RISK_CONTROLLER, ev.event_id, "recv")
router.subscribe(EventType.RESEARCH_REQUESTED, Role.BULL_AGENT, bull); router.subscribe(EventType.STRATEGY_AUTHORIZED, Role.RISK_CONTROLLER, pm)
try: router.run(AgentEvent(EventType.RESEARCH_REQUESTED, Role.MARKET_INTELLIGENCE))
except ValueError as e: print("        P12 router:", e)
ok("P12 Bull Agent emits STRATEGY_AUTHORIZED spoofing producer=PORTFOLIO_MANAGER", seen==[{"strategy_id":"rogue"}])
