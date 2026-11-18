# Phase 2 independent code audit — 2026-11-18

## Decision: FAIL — Phase 3 blocked

Scope reviewed: gateway, in-memory paper ledger, SQLite persistence, pending reservations, controller, synthetic stops, research pipeline, orchestrator, and the new unit tests. This is a source review, **not** a passing CI or runtime certification.

## Critical / high findings

1. **C1 — Untrusted booleans can authorize fills.** PendingOrders.fill now demands renewed booleans and matching strategy/symbol, but callers can still supply those booleans directly. The controller validates caller-supplied timestamps; there is no authenticated trusted data adapter or unforgeable authorization boundary. **OPEN.**
2. **C2 — Stops are not atomic or continuously scheduled.** The monitor writes a mark and then closes positions in separate transactions, leaving a race window. It has no continuous market feed, no outage policy, and no restart replay. **OPEN.**
3. **H1 — Audit log lacks tamper evidence.** Events are append-only by convention, but SQLite permits modifications. No hash chain or snapshot/event consistency validation. **OPEN.**
4. **H2 — No automatic UTC day roll.** Daily baseline is reset only on explicit invocation; repeated resets can evade daily-loss accounting. **OPEN.**
5. **H3 — No realistic fill economics.** Fees, spread, partial fills, latency, gaps, slippage, rejected orders and exchange reconciliation are absent. Stop gaps can exceed planned 1% risk. **OPEN.**
6. **H4 — Research and paper execution are disconnected.** The research backtest uses almost all available equity and does not route through guarded paper execution. No meaningful paper strategy performance can be inferred from it. **OPEN.**
7. **H5 — Persistence validation incomplete.** The state loader validates finiteness and nonnegative cash but does not prove positions and events reconcile; snapshot corruption or event deletion is not reliably detected. **OPEN.**
8. **H6 — Current test suite not verified.** Existing persistence tests originally called disabled direct entry; migrated to reservations, but no full current GitHub Actions run has been independently inspected. **PENDING CI.**
9. **H7 — Risk limit ambiguity.** Combined open risk is based on marked stop distance and not a worst-case loss bound. Pending reservations do not include fee buffers. **OPEN.**
10. **H8 — Local strategy isolation absent.** Standalone PaperDesk and PendingOrders are importable by any in-process code. A strategy can bypass the controller if granted database access. **OPEN.**

## Corrections committed during audit
- Disabled direct persistent entries, migrating tests to reservation/fill flow
- Revalidation flags required at fill rather than automatically reusing persisted flags
- Matching reserved strategy ID and symbol required at fill
- Explicit controller fill API rechecks allowlist and fresh observation

These corrections **do not resolve C1**, because the trust boundary still permits caller-supplied authorization/freshness claims.

## Release gate
- [ ] Latest CI green and all tests passing
- [ ] Independent, non-forgeable authorization and trusted feed freshness at fill
- [ ] Transactional stop processing and deterministic recovery
- [ ] Durable UTC daily-loss state, including restart behavior
- [ ] Tamper-evident audit + state/event consistency checks
- [ ] Failure-injection tests: duplicate orders, concurrent reservations, DB interruption, stale data, stop gaps, unexpected restart
- [ ] Realistic synthetic execution economics and accounting reconciliation
- [ ] End-to-end research-to-guarded-paper path

**No real-money deployment, unattended execution, or Phase 3 until release gate passes.**
