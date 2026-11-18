# 10 — Recommended roadmap

Principle: **prove an edge cheaply before building anything whose value depends on having one.** Every phase has an exit gate. If a gate fails, stop or go back; don't move on.

## Phase A — Evidence of edge (do first; ~$0)

| # | Task | Depends on | Acceptance criteria |
|---|---|---|---|
| A1 | Real OHLCV data for BTC/USD and ETH/USD from the intended venue at decision frequency, with a provenance file | — | SHA-256, venue, interval, retrieval date and gap report committed (data itself may stay out of git) |
| A2 | Research engine uses the ledger's sizing (1% risk), stops and cost model, or replays bars through `PendingOrders` | A1 | Same trades and P&L from backtest and ledger replay on a fixture |
| A3 | Benchmarks and nulls in every report: buy-and-hold, exposure-matched random | A2 | Report shows strategy rank among ≥ 200 nulls |
| A4 | Pre-register ≤ 3 hypotheses and their parameter sets; log every config tried via `audit.py` | A2 | Registry file committed before results |
| A5 | Untouched 12-month holdout evaluation | A3, A4 | **Gate:** net expectancy CI lower bound > 0 R/trade after tier-1 taker costs *and* beats ≥ 95% of nulls. **If no hypothesis passes, stop and rethink before Phase B.** |

## Phase B — Trustworthy paper execution (only after A5 passes)

| # | Task | Acceptance criteria |
|---|---|---|
| B1 | Fees, spread and slippage in ledger fills and exits; gross and net in events (F-04) | Unit tests; replay preserves fees |
| B2 | Fill at current trusted mark within tolerance; reservation TTL with auto-cancel event (F-09) | `test_a08` flips to pass (remove `@expectedFailure`) |
| B3 | Market-data adapter (exchange WebSocket/REST) inside the ledger process; mark timestamps and source (F-02, F-11) | Plausibility band (owner-set) rejects outliers; `test_a02`/`a03` pass |
| B4 | Ledger + gateway as a separate process with the API in `11` (F-01) | `PendingOrders` not importable by strategy code; `test_a01` rewritten against the API and passing |
| B5 | Watchdog: stale-data halt, auto-halt on daily-loss breach or reconcile failure, alert channel; documented resume procedure (F-10, F-11) | Fault-injection tests for each trigger |
| B6 | Concentration cap (owner-set) (F-05) | Gateway test |
| B7 | Daily `ledger_head()` anchoring outside the DB (F-07 residual) | Startup compares to last anchor |
| B8 | CI: SHA-pinned actions, 3.11 + 3.13 matrix, ruff, mypy (or pyright), coverage gate on `src/trading_desk/{gateway,pending_orders,persistent_paper}.py` | Branch protection on `main` |

**Exit gate B:** 30 days unattended on a $5–$10 VPS with zero replay discrepancies, zero unhandled exceptions, and every halt explained.

## Phase C — Paper track record

| # | Task | Acceptance criteria |
|---|---|---|
| C1 | Run the A5-approved strategy on paper until the pre-computed trade count (≈ 140 trades for +0.2R; `04`) | — |
| C2 | Compare paper fills against exchange prints at fill time | Mean slippage within the modelled assumption |
| C3 | Daily deterministic report + optional LLM narrative | Numbers come only from the ledger |

**Exit gate C:** paper net expectancy CI excludes zero and is consistent with the A5 estimate. Otherwise retire the strategy.

## Phase D — Minimal AI layer (optional)

The Research Assistant (offline, weekly) and later the Communicator (read-only + halt request), per `07`. **Acceptance:** a measurable improvement in Phase A outcomes per dollar spent (for example, more hypotheses passing A5 per month), or drop it.

## Phase E — Commercialization assessment

Only after C, and only with legal advice (`08`).

## Blockers and owner decisions needed

| Decision | Needed for |
|---|---|
| Venue (affects fees, data, minimum order size, legal availability in Canada) | A1, B1, B3 |
| Price plausibility band and stale-data timeout | B3, B5 |
| Concentration cap | B6 |
| Whether a daily-loss breach also flattens positions | B5 |
| Resume procedure after a halt (who, how, logged) | B5 |
| Budget split: paper research ≤ $10/month vs agent experimentation | D |

## What to remove, simplify or postpone now

- **Remove:** `risk.py` (dead); stale claims in `PHASE2_INDEPENDENT_AUDIT.md` (mark superseded); "no overnight positions" in `RESEARCH_LAB.md`.
- **Simplify:** 11 roles → the 5 components in `07`; one open-risk function used everywhere.
- **Postpone:** orchestrator, WhatsApp, Bull/Bear, multi-tenant work, Alpaca integration (until B4 exists).
