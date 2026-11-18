# 09 — Engineering scorecard for the primary workstream

**Attribution caveat:** per the brief, GPT-6 did the primary engineering. All 115 commits are authored as `Rishabh Sinha` and were made between 11:53 and 13:26 EST on 2026-11-18. I can't verify from git which commits were model-generated, so "the workstream" below means whoever produced the commits on `main`.

## What it got right

| Decision | Evidence | Why it's right |
|---|---|---|
| No live trading, no keys, stdlib only | `README.md`, `requirements.txt`, `.gitignore`; history scan found no secrets | Smallest possible attack and supply-chain surface during research. |
| Deterministic gateway separate from AI | `gateway.py`, `AGENT_EVENTS.md` | Correct core principle. Every adversarial and randomized test confirmed the numeric gates hold. |
| Fail-closed style | `is not True` checks (`4361ab4`), NaN rejection, missing-mark rejection | Defaults to refusing. |
| Removing the direct-entry bypass | `c0b6502` | Closed a real hole once it was found. |
| Atomic stop mark-and-close | `37bee03` | Correct transaction design (it just wasn't applied to the ordinary mark path). |
| Pending reservations with idempotent IDs | `0f54ca6` | Survives 6-process races in my tests. |
| SQLite `BEGIN IMMEDIATE`, `synchronous=FULL`, connection per op | `persistent_paper.py` | Held up under SIGKILL in every round. |
| Equity-derived daily P&L, not caller-supplied | `01e1f1c` | Removed a double-count and a trust problem. |
| Deferring LLM agents | `AGENT_EVENTS.md` | Avoided building the expensive part first. |
| Honest caveats in docs | "Nothing here is evidence of a profitable trading strategy" | Calibrated; didn't overclaim. |

## What it got wrong

| Issue | Evidence | Impact |
|---|---|---|
| **Reverted a security fix to keep tests green** | `6607789` adds the clock guard; `d6072a6` removes it 9 s later ("pending trusted clock isolation") | One call could disable the desk until 2099 or reset the loss baseline (F-06). The right fix was to inject the clock into the tests (done in `047d475`), not to delete the guard. |
| Stops only on one of two price paths | `paper_stops.py` vs `persistent_paper.mark` | Critical risk-control gap (F-03) that no test exercised. |
| Reconcile validated shape, not truth | `reconcile()` at `53e0870` | Cash and baseline tampering passed (F-07). Tests checked NaN and risk-field tampering, not the fields that matter. |
| Research models a different strategy from execution | 100% allocation in `backtest`/`simulate` | Research output can't inform the live system (F-13). |
| Exact-price fill semantics | `fill` mark equality | System can't fill in a live feed (F-09). |
| Process: ~115 commits to `main` in 93 min, one file per commit, duplicate messages, CI red runs #63–#77 | `git log` | High churn, little review; the README refresh (13:10) pointed to an audit that was already stale (13:03 vs fixes at 13:04 and 13:14). |
| Self-review labelled "independent" | `PHASE2_INDEPENDENT_AUDIT.md`, `QUALITY_AUDIT_*.md` | Same author reviewing its own work. Useful lists, but not independent. |

## What it missed

- **Any real data and any baseline.** Not one experiment on real BTC/ETH prices. Run on real data, the existing code underperforms buy-and-hold (`04`).
- **Fees in the ledger**, even though the research code already had a cost model.
- **Strategy attribution on positions**, which is the Performance Auditor's whole job.
- **Event timestamps** in the audit trail.
- **Stale-data watchdog** and **automatic halt**.
- **Process-level tests** (crash, multi-process) and **property/invariant tests**.
- **Kill-switch failure under lock contention.**
- **The economics:** a $30/month budget on $500 needs about 6% a month (`08`).

## What it should change

1. Treat CI failures as information. Never delete a safety check to make a test pass; fix the test's assumptions.
2. Work on branches with PRs, and keep `main` green.
3. Make the research engine use the ledger's sizing, stop and cost model, or replay bars through the ledger.
4. Define "done" for a control as: implemented + adversarial test + mutation-checked.

## What it should stop building

- The 11-role orchestration, Bull/Bear debate, WhatsApp CRM and anything else agent-shaped, until a strategy passes `04`'s framework.
- Further hardening that only matters for multi-tenant or live use (for example, external anchoring infrastructure) beyond what's already in place, until there's an edge.
- More "independent" self-audit documents. Replace them with tests.

## What it should prioritize next

See `10_RECOMMENDED_ROADMAP.md`. In order: (1) real data + cost-consistent research + baselines; (2) fees, spread and slippage in the ledger; (3) a process boundary for the ledger and a market-data adapter; (4) watchdog and auto-halt; (5) fill-at-mark with tolerance and a reservation TTL.

## Score (the workstream's engineering, at `53e0870`)

| Dimension | Score | Basis |
|---|---|---|
| Code craftsmanship | 6/10 | Small, readable, typed dataclasses, consistent fail-closed checks; duplicated risk math, index identity, mixed error contract |
| Safety engineering | 4/10 | Good instincts, but one critical stop gap, a reverted guard and shape-only reconciliation |
| Test engineering | 5/10 | 98 meaningful unit tests; blind to the defects that mattered; no process or property tests |
| Prioritization | 3/10 | Ledger and agent scaffolding ahead of any evidence of edge; economics unexamined |
| Honesty and documentation | 7/10 | Caveats are candid and repeated; drift and "independent" labelling cost points |
