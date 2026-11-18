# 03 — Code and security findings

**Audited commit:** `53e0870` (`main`, 2026-11-18 13:26 EST). **Fix branch:** `audit/independent-full-system-review`.
**Method:** I read every source, test, config and document file, then wrote exploit probes (`probe.py`, `probe2.py`; outputs reproduced below) and tests (`tests/test_audit_adversarial.py`, `tests/test_audit_resilience.py`). All of this ran in an isolated local paper environment, with no exchange access and no real orders.

Severity scale: **Critical** means it defeats a stated safety control or makes the accounting untrustworthy. **High** means the control can fail under realistic conditions. **Medium** means the failure needs a specific sequence of events or only affects auditability. **Low** covers hygiene and drift.

Status: **FIXED** means fixed on the audit branch with a regression test. **PARTIAL** means the main path is fixed but a residual risk remains. **OPEN** means not fixed. Open findings are recorded as `@expectedFailure` tests or as characterization tests.

## Summary

| ID | Severity | Title | Status |
|---|---|---|---|
| F-01 | Critical | Authorization is self-asserted, so any in-process caller can bypass the strategy allowlist | OPEN |
| F-02 | Critical | Prices are unauthenticated and unbounded; a forged mark followed by a close books fictitious P&L | OPEN |
| F-03 | Critical | A price crossing a stop via `observe()`/`mark()` never triggered the stop | FIXED |
| F-04 | High | Paper fills have no fees, spread, slippage, partial fills or minimum size | OPEN |
| F-05 | High | The 1% and 3% limits gate entries but do not bound losses; there is no automatic halt and no concentration cap | OPEN (characterized) |
| F-06 | High | Callers controlled the ledger clock; a security fix was reverted 9 s after it landed | FIXED |
| F-07 | High | Ledger tampering went undetected; events had no timestamps | PARTIAL |
| F-08 | Medium | Positions identified by list index, with no strategy attribution | FIXED |
| F-09 | Medium | Fills require mark == reserved price exactly; reservations never expire | OPEN |
| F-10 | High | Kill switch failed whenever another writer held the DB lock | PARTIAL |
| F-11 | Medium | No stale-data watchdog; marks carry no timestamp | OPEN |
| F-12 | Medium | An agent handler could emit events as another role | FIXED |
| F-13 | Medium | The research engine models a different strategy from the one execution would run | OPEN |
| F-14 | Medium | Mixed error contract: `False` vs `ValueError` vs `sqlite3.OperationalError` | OPEN |
| F-15 | Low | Dead and duplicated risk code; float money | OPEN |
| F-16 | Low | Documentation drift and self-labelled "independent" audits | OPEN (partly corrected in README) |
| F-17 | Low | CI/supply chain: tag-pinned actions, no lint/type/security gates, direct pushes to `main` | OPEN |

---

## F-01 — Authorization is self-asserted (Critical, OPEN)

**Where:** `src/trading_desk/pending_orders.py` (`reserve` lines 25–31, `fill` lines 92–96 at `53e0870`), `src/trading_desk/gateway.py` (`GatewayState.strategy_authorized`, `market_data_fresh`).

`GuardedPaperController` checks an allowlist. But `PendingOrders.reserve()` and `.fill()` are public and take `strategy_authorized=True, market_data_fresh=True` straight from the caller. The `is not True` type checks (commit `4361ab4`) block `1` or `"true"`, but they don't block a literal `True`. The allowlist itself is an in-memory `frozenset` supplied by whoever builds the controller. It isn't persisted or versioned.

**Reproduction** (`probe_baseline.txt` and `probe_after.txt`, both `DEFECT`):
```python
orders = PendingOrders(desk)            # no controller involved
orders.reserve("x", strategy_id="rogue-unapproved", symbol="BTC/USD", price=100,
               stop_price=95, quantity=1, strategy_authorized=True, market_data_fresh=True)  # True
orders.fill("x", strategy_authorized=True, market_data_fresh=True,
            expected_strategy_id="rogue-unapproved", expected_symbol="BTC/USD")          # True
```
Test: `test_audit_adversarial.TrustBoundaryTests.test_a01_*` (`@expectedFailure`).

**Why it matters:** the brief asks whether AI agents can bypass the risk gateway. They can't skip the *numeric* checks: every entry still passes `authorize()`. They *can* skip the strategy allowlist and the freshness check, because both are inputs the caller provides. The project's own audit (`docs/PHASE2_INDEPENDENT_AUDIT.md` C1) records this as open.

**Remediation:** run the ledger and gateway as a separate process (a small HTTP or Unix-socket service) that owns the SQLite file. Agents and strategies submit *intents*, never booleans. The service looks up strategy approval in a persisted, versioned `strategies` table and measures freshness from its own market-data adapter. Remove `strategy_authorized`/`market_data_fresh` from the public API. See `11_INTEGRATION_CONTRACT.md`.

## F-02 — Prices are unauthenticated and unbounded (Critical, OPEN)

**Where:** `paper_controller.py` `valid_observation`/`observe`; `persistent_paper.py` `mark`, `close`.

A `PriceObservation` is a plain dataclass built by the caller. The only checks are symbol, positivity, finiteness and age. The age check uses a timestamp that the caller also supplies. Nothing checks plausibility (for example, a jump size against the last trusted mark). `PersistentPaperDesk.mark()` and `.close()` are public, and `close()` requires the price to equal the current mark, which the caller has just set.

**Reproduction:**
```
DEFECT P2 controller accepts absurd price 1e9 with self-supplied timestamp
DEFECT P3 fabricated mark+close realizes P&L and passes restart reconcile pnl=999900 equity_after_restart=1000400.0
```
After the F-07 fix this is still undetected. The forged mark is faithfully logged, so replaying the log reproduces the fictitious P&L. Integrity checks can show that state matches its history. They can't show that the history matches the market. A hallucinated price from an agent behaves the same as a forged one.

**Remediation:** (1) Only a trusted market-data adapter may call `mark`, and only from inside the ledger process. (2) Each observation should carry its source, the exchange timestamp and a sequence number. (3) Reject marks that move more than a configured band from the last trusted mark unless a second source confirms them. The band is a new risk parameter, so the owner should choose it; I did not invent one. (4) `close` should take the price from the trusted mark, not from an argument. Tests: `test_a02_*`, `test_a03_*` (`@expectedFailure`).

## F-03 — Stops skipped on ordinary marks (Critical, FIXED)

**Where (baseline):** `persistent_paper.py` `mark()` (lines 150–152) only called `PaperDesk.mark`. Stops were evaluated only in `apply_stop_mark()`, which is reached only through `paper_stops.process_stop_observation`. `GuardedPaperController.observe()` and `.reserve()` both update marks through `mark()`.

**Reproduction on `53e0870`:** entry at 100 with stop 95, then `observe(80)`. The position stays open. A later stop observation at 96 does nothing because 96 > 95. A position that traded 15% through its stop is never exited, and planned risk becomes meaningless.
```
DEFECT P4 price observed at 80 (< stop 95) via observe() leaves position open; next stop check at 96 does nothing positions=1
```
**Fix:** commit `4de8e29`. `mark()` now applies the mark and closes every crossed stop at the observed price in the same transaction, sharing `_mark_and_stop` with `apply_stop_mark`. The event records the exits. Tests: `test_a04_any_mark_through_stop_closes_position`, plus the randomized invariant "every open position's mark is above its stop" (`test_audit_resilience.RandomizedInvariantTests`). Mutation check: disabling the stop branch fails 16 tests.

## F-04 — No execution costs in paper fills (High, OPEN)

**Where:** `paper_desk.py` `enter`/`close`; `pending_orders.py` `fill`.

Entries and exits settle at exactly the mark, with zero fees, spread or slippage, no partial fills and no minimum order size. The research backtester charges basis-point costs, but the ledger the strategy would actually be judged on does not. At published tier-1 fees, round-trip costs on a 1%-risk position are 0.15R–1.6R per trade depending on venue and stop distance (see `08_COST_AND_COMMERCIALIZATION.md`). Paper P&L will be overstated by that amount on every trade.

**Remediation (smallest credible model):** charge a configurable taker fee on both legs, cross a half-spread on entry and exit, and apply a configurable slippage on stop exits (which are market orders). Enforce the venue's minimum notional and increment. Reserve fee headroom in `reserve` (cash and risk). Log fee, spread and slippage as separate fields in the fill and close events, so the auditor can report gross and net figures.

## F-05 — Limits gate entries; they do not bound losses (High, OPEN — characterized)

**Where:** `gateway.py` lines 70–74; `paper_stops.py` docstring (which correctly warns about gaps).

The 1% combined planned-risk limit and the 3% daily-loss threshold are implemented correctly *as entry gates*. The randomized tests confirm that no fill ever leaves combined open risk above 1% of equity, and that no entry is accepted after a breach. They are not loss limits:

- **Gap:** positions of 2.5 BTC-units and 2.4 ETH-units (both with stops 1% below entry) total 0.98% planned risk and $490 notional. Simultaneous gaps to 93 and 92 realize a **$36.70 loss (7.34%)**. Test: `test_a05_gap_can_exceed_daily_threshold_but_new_risk_is_refused`.
- **No automatic halt or flatten:** a breach only blocks *new* entries. The kill switch is never engaged automatically, and open positions are not reduced.
- **No concentration cap:** with a 1% stop, the 1% risk rule allows a $500 notional, which is 100% of equity in one asset. Gap exposure scales with notional, not with planned risk.

**Remediation (owner decisions; I did not change any limit):** add a maximum notional per position and in total (for example ≤ 50% of equity per asset); automatically engage the kill switch and optionally flatten on breach; and report the realized-loss distribution, not just planned risk.

## F-06 — Caller-controlled clock (High, FIXED)

**Where (baseline):** `persistent_paper.py` `roll_utc_day(now=...)` lines 189–212; `paper_controller.py` `valid_observation(now=...)`.

Commit `6607789` (13:15:58) added a ±120 s guard on caller-supplied `now`. Commit `d6072a6` (13:16:07, nine seconds later) removed it with the message *"Preserve deterministic test clock injection pending trusted clock isolation."* The guard broke tests that passed `now=tomorrow`, and the fix was reverted to keep CI green.

**Reproduction on `53e0870`:** `desk.roll_utc_day(now=datetime(2099,1,1))` succeeds and resets the daily-loss baseline. Every later `reserve()` then raises `ValueError: Clock rollback detected` until 2099, which means a single bad call permanently disables the desk. The controller also accepts an observation 30 days in the future if the caller passes a matching `now`.

**Fix:** commit `047d475`. The trusted clock is injected once at construction (`PersistentPaperDesk(path, clock=...)`). `roll_utc_day` and the controller reject any `now` more than 120 s from it. Tests inject a deterministic clock instead of passing arbitrary times. Tests: `test_a06_*`, `test_a14_restart_after_utc_midnight_rolls_once`. **Residual:** an in-process caller can still construct a desk with a fake clock. Process isolation (F-01) is what closes that.

## F-07 — Ledger tampering undetected; no event timestamps (High, PARTIAL)

**Where (baseline):** `persistent_paper.py` `reconcile()` lines 96–138; `events` schema line 26 (`seq, kind, payload` only).

**Reproduction on `53e0870`:** set `cash_usd` and `day_start_equity_usd` to 1,000,000 and `DELETE FROM events`. Restart passes, and `reconcile()` returns equity 1,000,000. Raising `day_start_equity_usd` also evades the daily-loss gate.

**Fix:** commit `ebdcd5d`. Events now carry `created_at_utc` (trusted clock) and a SHA-256 hash chain (`prev_hash`, `hash`). At startup, `reconcile()` verifies the chain and **replays every event** (marks with stop exits, closes, fills re-run through `PaperDesk.enter` and the gateway, halts and day rolls). The replay must reproduce the stored snapshot exactly, and reservation statuses must agree with the log. Fill events now carry their economics. `verify_integrity()` and `ledger_head()` are exposed. Databases created by `main` migrate in place (verified with a database built by the `main` worktree). Tests: `test_a07*`, `test_a11_events_are_timestamped`, and replay after every SIGKILL round.

**Residual:** an attacker who can rewrite *both* tables and recompute the chain is not detected. Mitigation: publish `ledger_head()` to an append-only location outside the database daily (for example a signed git tag or an e-mail to yourself), and compare on startup.

## F-08 — Index-based position identity; no attribution (Medium, FIXED)

**Reproduction on `53e0870`:** positions have stops [98, 96, 90]. A stop at 97.5 closes the first one. A caller that read the snapshot earlier calls `close(1, 97.5)` intending stop=96, and the position with stop=90 is closed instead. `PaperPosition` had no `strategy_id` or `order_id`, so per-strategy P&L, which is the Performance Auditor's core job, could not be computed.

**Fix:** commit `db922b1`. `PaperPosition.strategy_id` and `order_id` were added. `close_position(order_id, price)` was added. Close and stop events now record attribution and per-exit P&L. Tests: `test_a09_*`, `test_a10_*`.

## F-09 — Exact-price fill liveness (Medium, OPEN)

**Where:** `pending_orders.py` fill (`desk.marks.get(symbol) != payload["price"]`); `paper_controller.py` fill line 80.

A fill succeeds only if the current mark equals the reserved price exactly. In any live feed, the next tick moves the mark, so the reservation can no longer be filled. Reservations never expire, so the reserved cash and risk stay locked and block new orders until someone cancels them.
```
DEFECT P8 one-cent move makes reservation unfillable; its risk stays locked and blocks new orders
```
**Remediation:** fill at the current trusted mark within a configured tolerance of the reserved price. Re-size or reject the order if risk at the fill price exceeds the reservation. Add a reservation TTL with automatic cancellation and an event. Test: `test_a08_*` (`@expectedFailure`).

## F-10 — Kill switch failed under DB contention (High, PARTIAL)

**Reproduction on `53e0870`** (`probe2_baseline.txt`): with another connection holding `BEGIN IMMEDIATE`, `halt()` blocked for 10.02 s, raised `OperationalError: database is locked` and left `kill_switch=False`. A concurrent `reserve()` also blocked for 10.03 s.

**Fix:** commit `f91714a`. `halt()` writes and fsyncs `<db>.HALT` *before* the SQLite write. `reserve()` and `fill()` refuse new risk when the flag exists, without touching the DB. A flag found at startup is applied to the persisted switch. After the fix, a `reserve()` during a contended halt was refused in 0.00 s. The DB write in `halt()` can still time out (the flag is honoured anyway). Tests: `test_a13_*`, `test_database_unavailable_never_approves_and_halt_still_blocks`.

**Still open:** the switch is never engaged automatically (on a daily-loss breach, stale data, a reconcile failure or repeated errors). It doesn't cancel pending reservations. There is no documented resume procedure, and the DB switch is permanent.

## F-11 — No stale-data watchdog (Medium, OPEN)

Marks are stored without timestamps (`state.marks` is `{symbol: price}`). Equity, the daily-loss gate and the UTC-day baseline use whatever mark was last written, however old it is. Nothing detects that observations have stopped arriving, and positions would stay open with no stop evaluation. **Remediation:** store `(price, observed_at, source)` per mark. Refuse entries and engage the halt when any open-position mark is older than N seconds (owner parameter). Alert through the CRM channel.

## F-12 — Agent producer spoofing (Medium, FIXED)

**Reproduction on `53e0870`:** a Bull Agent handler returns `AgentEvent(STRATEGY_AUTHORIZED, producer=PORTFOLIO_MANAGER)`. `validate_event` checks only the claimed producer, so the router delivers it. **Fix:** commit `15840d3`. The router rejects proposed events whose producer differs from the handler's registered role. Test: `test_a12_*`. This is not authentication (see `docs/AGENT_EVENTS.md`), and the orchestrator is not connected to execution.

## F-13 — Research models a different strategy from execution (Medium, OPEN)

`research.backtest` (line 91) and `simulator.simulate` (line 55) invest **100% of cash** when long, with no stop. Execution sizes positions to 1% risk with a stop. Backtest returns, drawdowns and trade counts therefore say nothing about the system that would trade. `pipeline.py` line 55 also hard-codes `500.0`. Details are in `04_QUANTITATIVE_REVIEW.md`.

## F-14 — Mixed error contract (Medium, OPEN)

`reserve()`/`fill()` return `False` for most rejections. They raise `ValueError` on clock rollback and raise `sqlite3.OperationalError` on lock timeout or a missing DB (`test_database_unavailable_*`). Each of these fails closed, but an agent retry loop that treats exceptions as transient would hammer the ledger. **Remediation:** return a typed result (`accepted | rejected(reason_code) | unavailable(retry_after)`). See `11_INTEGRATION_CONTRACT.md`.

## F-15 — Dead/duplicated code, float money (Low, OPEN)

`risk.check_proposed_risk` is used only by its own tests. The open-risk formula is duplicated in `paper_desk.enter`, `pending_orders.reserve` and `pending_orders.fill`. Money is `float`, which is acceptable for paper trading but should become `Decimal` or integer micro-units before any broker reconciliation. There are function-local imports (`from math import isfinite` inside `_load` and `reconcile`).

## F-16 — Documentation drift (Low, OPEN)

- `docs/PHASE2_INDEPENDENT_AUDIT.md` (commit `c0de95a`, 13:03) lists C2 (non-atomic stops) and H2 (no automatic roll) as **OPEN**. They were fixed in `37bee03` (13:04) and `4dc5c5a` (13:14), and the README refreshed at 13:10 still points to it.
- `docs/RESEARCH_LAB.md` line 19 says "no overnight positions", which contradicts the README's 24/7 policy.
- `docs/PROGRESS.md` contains a literal `\n`.
- `docs/TOOLS.md` and `ARCHITECTURE.md` mention "Wendy" without defining it.
- Both earlier audits are labelled "independent" but come from the same workstream that wrote the code. They are honest about their limits, but they are self-reviews.

## F-17 — CI and supply chain (Low, OPEN)

Positives: there are zero runtime dependencies, and no secrets were found anywhere in the git history (the full history was scanned for key patterns). Gaps: `actions/checkout@v4` and `setup-python@v5` are pinned by tag, not by SHA. CI tests only Python 3.11. There is no lint, type check, coverage gate or dependency or secret scanning. All 115 commits went directly to `main`, and the README records failing CI runs #63–#77 on `main`.

---

## Interface changes made on the audit branch

| Change | Compatibility |
|---|---|
| `PersistentPaperDesk(path, initial_equity=500.0, *, clock=None)`; `now()`, `check_caller_time(now)` | Additive. A caller-supplied `now` more than 120 s from the trusted clock now raises. |
| `GuardedPaperController.*(…, now=None)` | `now` is optional; if given, it must agree with the desk clock. |
| `PersistentPaperDesk.mark()` closes crossed stops and returns `(triggered, realized_pnl)` | Behavioural change (it previously returned `None` and never stopped out). |
| `PaperPosition.strategy_id`, `.order_id`; `PaperDesk.enter(order_id="")`; `index_of()` | Additive, with defaults. |
| `PersistentPaperDesk.close_position(order_id, price)` | Additive. `close(index, price)` is kept. |
| `events` table: `created_at_utc`, `prev_hash`, `hash`; fill events carry economics | Migrated automatically. Startup now fails closed if replay disagrees with the snapshot. |
| `verify_integrity()`, `ledger_head()` | Additive. |
| `halt()` writes `<db>.HALT`; `halt_requested()`, `halt_flag_path` | Entries are refused while the flag exists. Deleting the flag is the only way back, and only for the flag. |
| Orchestrator rejects proposed events whose producer ≠ handler role | Stricter. |
