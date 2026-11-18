# 05 — Test results

## Environment

- Workspace: isolated Linux container, no exchange connectivity (exchange API hosts were unreachable from it), no credentials.
- Interpreters: CPython **3.11.18** (the CI version) and **3.13.18**.
- Install: `python -m pip install -e .` (zero runtime dependencies).

## 1. Baseline: existing suite at `53e0870` (`main`)

```bash
git checkout 53e0870
python -m pip install -e .
python -m compileall -q src tests      # exit 0
python -m unittest discover -s tests -v
```

| Interpreter | Tests | Result | Log |
|---|---|---|---|
| 3.13.18 | 98 | **OK** (0 failures, 0 errors) | `evidence/baseline_py313.txt` |
| 3.11.18 | 98 | **OK** | `evidence/baseline_py311.txt` |

The README cites 90 tests at `4361ab4`. Eight more were added afterwards, up to `53e0870`. **All 98 pass, yet seven Critical/High defects in `03` reproduce at that commit.** A green suite was not evidence of safety.

### What the existing tests prove, and what they don't

| Area | Existing coverage | Gap that let a defect through |
|---|---|---|
| Gateway arithmetic | Good: kill switch, unauthorized, stale, daily realized/unrealized/combined loss, combined risk, no-short, NaN | Tests call `authorize()` with hand-built state; they don't test who supplies the booleans (F-01). |
| Ledger entries/closes | Good unit coverage, fail-closed on missing marks, NaN, overspend | No test marks through a stop via `mark()`/`observe()` (F-03). |
| Persistence | Restart, kill-switch persistence, corrupt NaN state, tampered reservation economics, tampered `risk_usd` | No test edits `cash_usd` or `day_start_equity_usd`, or deletes events (F-07). These are the edits that matter. |
| UTC roll | Once per day, rollback rejected | Tests *depend on* passing an arbitrary `now`. That is why the guard in `6607789` was reverted in `d6072a6` (F-06). |
| Concurrency | 16 threads × same order → 1 success | Threads only; no separate processes, no crash during a transaction. |
| Research | Causality, cost monotonicity, validation | Synthetic linear series only; nothing on real data, no baseline, no selection-bias check. |
| Orchestrator | CRM cannot emit authority events | No test of producer spoofing by other roles (F-12). |

## 2. Defect reproduction against `main` (probes)

`evidence/probe.py` and `evidence/probe2.py` run against the `main` worktree and against the audit branch. Full output is in `evidence/probe_baseline.txt`, `probe_after.txt`, `probe2_baseline.txt` and `probe2_after.txt`.

| Probe | `main` (53e0870) | Audit branch |
|---|---|---|
| P1 unapproved strategy fills via `PendingOrders` | DEFECT | DEFECT (F-01 open) |
| P2 price 1e9 accepted | DEFECT | DEFECT (F-02 open) |
| P3 forged mark + close books $999,900 and passes restart | DEFECT | DEFECT (F-02 open; replay-consistent) |
| P4 observe(80) below stop 95 leaves position open | DEFECT | **fixed** |
| P5 simultaneous gap loses 7.34% with 0.98% planned risk | DEFECT | characterization (F-05) |
| P6 `roll_utc_day(now=2099)` bricks desk | DEFECT | **fixed** (rejected) |
| P7 cash/baseline tamper + event deletion pass restart | DEFECT | **fixed** (detected) |
| P8 one-cent move makes reservation unfillable | DEFECT | DEFECT (F-09 open) |
| P9 index-based close hits the wrong position | DEFECT | **fixed** (`close_position`) |
| P10 no strategy/order attribution | DEFECT | **fixed** |
| P11 events untimestamped | DEFECT | **fixed** |
| P12 Bull Agent spoofs Portfolio Manager | DEFECT | **fixed** |
| Kill switch under lock: `halt()` | raises after 10.02 s, not halted | DB write still times out, **but entries refused in 0.00 s** via flag |
| Throughput (200 reserve+fill, 200 positions) | 238 pairs/s; stop-mark 452/s | 199 pairs/s; stop-mark 301/s (hash chain + per-op timestamp) |

## 3. Final suite on the audit branch (`1348273`)

```bash
git checkout audit/independent-full-system-review
python -m pip install -e .
python -m compileall -q src tests
python -m unittest discover -s tests -v
```

| Interpreter | Tests | Result | Log |
|---|---|---|---|
| 3.13.18 | 127 | **OK (expected failures=4)** | `evidence/final_py313.txt` |
| 3.11.18 | 127 | **OK (expected failures=4)** | `evidence/final_py311.txt` |

The four expected failures are open defects with tests that assert the safe behaviour: F-01 (`test_a01`), F-02 (`test_a02`, `test_a03`) and F-09 (`test_a08`). When one of them is fixed, unittest reports an *unexpected success* and the decorator must be removed deliberately.

### Existing tests changed (setup only)

Three test modules were changed to inject a deterministic trusted clock, because the ledger now rejects arbitrary caller times. No assertion was removed or weakened. `test_utc_roll_survives_restart_and_rejects_rollback` now pins the rejection reason (`"rollback"`) instead of accepting any `ValueError`.

- `tests/test_paper_controller.py`: `PersistentPaperDesk(..., clock=lambda: self.now)`
- `tests/test_paper_stops.py`: same
- `tests/test_persistent_paper.py`: mutable clock; `tomorrow` is set on the clock rather than passed only as an argument.

### New tests (29)

**`tests/test_audit_adversarial.py` (20)**

| Test | Proves |
|---|---|
| `test_a01`, `a02`, `a03`, `a08` | Open defects (expected failure) |
| `test_a04_any_mark_through_stop_closes_position` | F-03 fix |
| `test_a05_gap_can_exceed_daily_threshold_but_new_risk_is_refused` | Entry gate ≠ loss bound (characterization; passes on `main` too) |
| `test_a06_*`, `test_a06b_*` | F-06: arbitrary clock rejected at roll and at observation |
| `test_a14_restart_after_utc_midnight_rolls_once` | Restart after midnight rolls once, positions preserved, baseline = marked equity |
| `test_a07`, `a07b`, `a07c`, `a07d` | Detect state edit (cash, baseline), event deletion, event edit |
| `test_a07e`, `test_a11` | Valid ledger verifies; head hash exposed; events timestamped |
| `test_a09`, `test_a10` | Close by order ID after an index shift; attribution on positions and exits |
| `test_a12` | Producer spoofing rejected |
| `test_a13` | Entries refused within 1 s while `halt()` waits on a locked DB; switch persisted after |
| `test_reserve_refuses_cash_over_commitment` | Added because the cash-check mutant survived (below) |

**`tests/test_audit_resilience.py` (9)**

| Test | Proves |
|---|---|
| `test_failure_inside_fill_rolls_back_everything` | Exception after `desk.enter`, before commit → no cash, position or status change; fill succeeds after |
| `test_failure_inside_close_rolls_back_everything` | Same for close |
| `test_database_unavailable_never_approves_and_halt_still_blocks` | DB file disappears → reserve raises (never approves); halt flag still blocks; switch applied at restart |
| `test_sigkill_during_trading_never_corrupts_ledger` | Two worker **processes** trade; SIGKILL at random times in 6 rounds; after each, restart replays the full log and `cash + Σ position cost = 500` |
| `test_parallel_processes_cannot_exceed_combined_risk` | 6 processes released at the same instant, each with a max-risk order → exactly 1 succeeds |
| `test_parallel_processes_cannot_reuse_order_id` | 6 processes, same order ID → exactly 1 succeeds |
| `test_random_sequences_preserve_accounting_invariants` | 12 seeds × 150 random ops (marks ±4%, reserve, fill, cancel, close, day rolls). After every op: cash ≥ 0; risk = (entry−stop)×qty; every open mark > its stop; equity = cash + Σ qty×mark. After every fill: combined open risk ≤ 1% equity; no entry/fill after a 3% breach. Replay verifies at the end. Across the 12 seeds: 538 marks, 26 marks with stop exits, 215 reserves, 76 fills, 46 closes, 135 cancels, 126 day rolls |
| `test_deterministic_replay_produces_identical_ledger` | Same seed twice → identical snapshot and identical head hash |
| `test_ledger_throughput_and_startup_verification_budget` | 150 reserve+fill < 10 s; full replay at startup < 5 s |

## 4. Do the tests have teeth? (mutation check)

I injected each of the faults below into the source and ran the full suite (`evidence/mutation.txt`):

| Mutant | Result |
|---|---|
| M1 combined risk cap 1% → 2% | caught (9 failures) |
| M2 daily-loss gate disabled | caught (4) |
| M3 stop branch disabled in `_mark_and_stop` | caught (16) |
| M4 pending reservations' risk ignored at reserve | caught (4) |
| M5 replay-vs-snapshot comparison disabled | caught (2) |
| M6 kill switch ignored by gateway | caught (2) |
| M7 halt flag ignored by reserve/fill | caught (1 failure, 1 error) |
| M8 reserve-time cash check removed | **survived**, so `test_reserve_refuses_cash_over_commitment` was added → caught (1) |

## 5. Not executed, and why

- **Real exchange paper trading or broker reconciliation.** Out of scope and not authorized; exchange hosts are unreachable from the workspace.
- **Long-duration soak tests** (days of unattended running). Not feasible here. Recommended before any unattended run (see `10`).
- **Property tests with Hypothesis.** The project is stdlib-only, so I used seeded `random` sequences, which also gives deterministic replay. Adding Hypothesis is reasonable as a dev-only dependency.
- **Power-loss durability.** SIGKILL tests process death, not OS or disk loss. `synchronous=FULL` with the default rollback journal is the right setting, but I did not verify it under power loss.
