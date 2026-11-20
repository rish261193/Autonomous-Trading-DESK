# 06 — Risk and accounting review

**The key distinction.** The system *refuses new risk* correctly. It does *not* guarantee a maximum realized loss. Those are different properties, and the docs, the README in particular, should never imply the second.

## Control-by-control verification

| Control | Where | Implemented as | Verified by | Verdict |
|---|---|---|---|---|
| 1% combined planned risk | `gateway.py:73`; open risk computed in `pending_orders.reserve/fill`, `paper_desk.enter` | `new_risk + Σ open (max(entry, mark) − stop)·qty + Σ pending risk ≤ 1% × marked equity` | Unit tests; 6-process race; randomized invariant after every fill (12 seeds); mutant M1/M4 caught | **Correct as an entry gate.** Uses *current* equity, so the dollar budget shrinks after losses. Open risk is measured from `max(entry, mark)`, so after a gain the locked-in profit counts as risk. Conservative, but it also blocks new trades after winners. |
| 3% daily loss threshold | `gateway.py:70` with `daily_realized = equity − day_start` | Blocks entries when marked equity ≤ 97% of day-start equity | Unit tests; randomized invariant; mutant M2 caught | **Correct as an entry gate.** It doesn't halt, flatten or cancel pending reservations. Losses past 3% are possible (gap: 7.34%, `test_a05`). |
| Cash availability | `pending_orders.reserve` (`notional + Σ pending ≤ cash`), `fill`, `paper_desk.enter` | Three checks | `test_reserve_refuses_cash_over_commitment` (added; mutant M8 previously survived) | Correct. |
| Pending reservations | `reservations` table | Reserved cash and risk count against limits | Restart, cancel and idempotency tests; process races | Correct, but **reservations never expire**, and exact-price fills make them stick (F-09). |
| Open-position exposure | marks × qty | Mark-to-market | Randomized `equity == cash + Σ qty·mark` | Correct given trusted marks (F-02). |
| Realized P&L | `PaperDesk.close` | `qty × (exit − entry)`; fees not modelled | Unit tests; replay equality | Correct arithmetic, **gross of costs** (F-04). |
| Unrealized P&L | implicit in equity | — | — | Correct, but marks have no age (F-11). |
| Net equity | `PaperDesk.equity()` | cash + Σ qty·mark; fails closed on a missing mark | Tests | Correct. |
| Stop handling | `_mark_and_stop` (after fix) | Any mark ≤ stop exits at the observed price (gap-aware) | `test_a04`; randomized "mark > stop" invariant; M3 caught | **Was broken on `main`** (F-03); fixed. Still not a real stop order: no slippage beyond the observed print, no exchange-side stop. |
| UTC accounting | `roll_utc_day`, `daily_clock` table | Once per UTC date, transactional, before reserve/fill; rollback rejected | `test_a14` (restart after midnight); persistence tests | **Correct after F-06 fix.** Two caveats: the roll happens lazily, only on reserve/fill; and the baseline uses the last marks, which may be stale. |
| Kill switch | `halt()`, gateway first check, `<db>.HALT` flag (after fix) | Blocks reserve and fill; persists | `test_a13`, `test_database_unavailable_*`, M6/M7 caught | **Partial.** Manual only, never automatic; doesn't cancel reservations; no resume procedure. |
| Restart recovery | `reconcile()` + `_verify()` (after fix) | Structural checks, SQLite `quick_check`, hash chain, full replay equality | SIGKILL rounds; tamper tests | **Strong for a single-file ledger.** Residual: a full rewrite of both tables with a recomputed chain (F-07). |

## Adverse scenarios (from the brief)

| Scenario | What happens (audit branch) | Evidence |
|---|---|---|
| BTC falls sharply through the stop | The next mark at or below the stop closes the position **at that mark**. On `main` this only happened through `process_stop_observation`; a mark via `observe()` silently skipped it. | `test_a04`, `test_stop_executes_at_gapped_price_not_stop_price` |
| BTC and ETH fall together | Each symbol's stops fire on its own mark. Combined planned risk 0.98% → realized 7.34% on a 7–8% gap. New entries then refused. **No automatic halt.** | `test_a05` |
| Two agents submit simultaneously | `BEGIN IMMEDIATE` serializes. 6 processes, combined-risk race → 1 accepted. Same order ID → 1 accepted. | `test_parallel_processes_*`, `test_parallel_reservations_never_exceed_risk` |
| Market observations stop arriving | **Nothing happens.** Positions keep their last mark and no stop is evaluated. No alert, no halt. | F-11 (open) |
| Database unavailable | Reserve raises `sqlite3.Error`; it never approves. `halt()` still sets the flag, entries are refused, and the switch is applied at the next startup. | `test_database_unavailable_*` |
| Process crash during execution | All-or-nothing per operation. After SIGKILL in 6 random rounds, restart replays the log and accounting balances. | `test_sigkill_*`, fault-injection tests |
| Restart after UTC midnight | First reserve/fill (or explicit `roll_utc_day()`) rolls once. The baseline is marked equity; positions are kept. | `test_a14` |
| Reservation duplicated | Order ID is the primary key; the same ID is rejected forever, even after cancel. | `test_duplicate_order_id_never_reused`, process race |
| Unauthorized strategy ID | Rejected by `GuardedPaperController`. **Accepted** by `PendingOrders` called directly with `strategy_authorized=True`. | `test_a01` (expected failure, F-01) |
| Loss beyond the daily threshold because of a gap | Realized; new entries refused; existing positions untouched; pending reservations remain (fill blocked). | `test_a05` |

## Execution modelling (accounting impact)

Paper P&L is gross. For a 1%-risk ($5) trade at tier-1 published fees, round-trip fees alone are:

| Stop distance | Notional | Alpaca taker 0.25% | Kraken Pro taker 0.80% |
|---|---|---|---|
| 1% | $500 | $2.50 (0.50R) | $8.00 (1.60R) |
| 2% | $250 | $1.25 (0.25R) | $4.00 (0.80R) |
| 5% | $100 | $0.50 (0.10R) | $1.60 (0.32R) |

Spread and stop slippage come on top of that. Sources and caveats are in `08`. **A strategy with less than about +0.3R gross expectancy per trade can't survive tier-1 taker costs at tight stops.** The ledger as it stands would report it as profitable.

## Required before any unattended paper run

1. Fees, spread and slippage in the ledger (F-04), with gross and net reported separately.
2. Stale-data watchdog: mark timestamps, an automatic halt when stale, and alerts (F-11).
3. Automatic kill switch on daily-loss breach, reconcile failure or repeated errors, plus a written resume procedure (F-10).
4. Concentration cap on notional (F-05). The limit is the owner's call.
5. Reservation TTL and fill-at-current-mark within tolerance (F-09).
6. Ledger and gateway in their own process, so that F-01 and F-02 become enforceable.
