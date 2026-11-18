# Quality audit — 2026-11-18

## Verdict
**NOT RELEASE-READY. NOT APPROVED FOR BROKER-CONNECTED PAPER TRADING OR LIVE TRADING.**
This is a source review and historical CI-log inspection, not a completed exhaustive dynamic, security, or integration audit. No profitability claims.

## Evidence
- GitHub Actions run 44355492100: 39 tests discovered, 3 failed, 2 import errors; previous defects were literal escaped newlines and midnight liquidation.
- GitHub Actions run 44355952112: 42 tests discovered, 41 passed, 1 test module import error from literal escaped newlines. That file was subsequently corrected in commit 5f3ef3e. **A successful CI run after that commit was not independently confirmed by this audit.**
- Source files reviewed: research, simulator, signals, strategies, pipeline, metrics, validation, audit, risk, gateway, tools, agent contracts, orchestrator, configuration, CI workflow, and project documentation.

## Findings

### Critical — deployment blockers
1. **Risk gateway disconnected from backtests and execution.** Neither `research.backtest` nor `simulator.simulate` invokes `gateway.authorize`. There is no broker order boundary. Never infer that 1% trade risk or 3% daily drawdown is enforced.
2. **No trusted persisted portfolio state or broker reconciliation.** `GatewayState` accepts caller-provided booleans and P&L. No authenticated strategy authorization, fresh market-data proof, pending-order accounting, persistent kill switch, exchange reconciliation, or fail-closed order integration exists.
3. **No protective stops or position sizing based on stop distance.** The simplified backtests invest all available cash when long. This is not a 1% loss-risk model; large adverse moves can lose far more than the intended risk budget.

### High — research correctness
4. **SMA input validation incomplete.** `backtest` does not reject non-finite capital/costs, excessively large transaction costs, noninteger window inputs, or malformed `Costs` values. `grid_search` can silently ignore invalid combinations.
5. **Daily loss calculation is not independently verified.** Preliminary gateway sums supplied realized/unrealized P&L and uses UTC day-start equity. The definitions, timestamp boundary, carried-position basis and prevention of double counting require a formal ledger.
6. **Execution model optimistic/incomplete.** Signals use prior closes and fills occur at current close; no spread/order-book dynamics, latency, minimum size, partial fills, exchange outages, market impact, or gap/slippage stress tests.
7. **No integrated cross-family rolling validation.** `pipeline.research_pipeline` only selects SMA parameters; momentum, mean-reversion and breakout use a separate simulator/screener.
8. **Research metrics can mislead.** `pipeline` calculates a two-point return using hardcoded $500 and independent window equity; no continuous mark-to-market portfolio across folds, benchmark, statistical uncertainty, or exposure-adjusted return.

### Medium — authorization, robustness, reproducibility
9. **Agent identity spoofing.** `AgentEvent.producer` and registry role strings are user-supplied labels, not authenticated principals; `Orchestrator` validates event shape but not provenance. CRM cannot emit authority events in one code path, but the system lacks a security boundary.
10. **Audit trail is not tamper-evident.** JSONL is append-only by convention, without atomic writes, locking, hash chaining, or trusted source metadata.
11. **Unbounded/unsafe input edge cases.** Some numeric type errors propagate instead of cleanly rejecting; `signal_at` permits index == len(closes) (valid as a next-bar signal, but contract should say so); `ToolRegistry.invoke` catches a limited exception set; `Orchestrator.history` accumulates across calls.
12. **No data quality policy enforcement.** Strict chronological timestamps and positive closes are checked, but missing bars, duplicated venue data, anomalous spikes, data provenance, and exchange-specific adjustments are not validated.
13. **Incomplete automated verification.** CI runs only unit tests under Python 3.11. No formatting/lint, static typing, security scanning, coverage thresholds, property-based tests, mutation tests, reproducibility snapshots, or end-to-end paper simulation.
14. **Documentation drift.** `docs/EVALUATION.md` still describes first-next-day liquidation; `docs/PROGRESS.md` says only one strategy family exists and contains a literal backslash-n.

## Confirmed alignment
- Exactly eleven role identifiers are defined.
- Only BTC/USD and ETH/USD spot buy intents are allowed by the preliminary gateway.
- No broker placement function or live-money execution is implemented in the inspected research registry.
- Research/simulator logic no longer contains the former midnight forced-close branch in the latest fetched source.
- CI configuration installs the package and invokes unittest discovery on pushes.

## Required release gates
1. Confirm a successful CI run on the exact current main commit.
2. Add syntax/format, static analysis and boundary/property tests.
3. Implement and verify deterministic portfolio accounting, mark-to-market P&L, position sizing, risk state persistence, and execution-boundary authorization.
4. Reconcile cost/fill model against exchange paper fills and run stress scenarios.
5. Consolidate strategy-family validation with train-only selection, embargoes, and true out-of-sample holdouts.
6. Establish trusted event identity and enforce CRM/execution separation at authority boundaries.
7. Resolve documentation drift, version data/strategy artifacts, and produce a reproducible evidence pack.
8. Re-audit after fixes. Green unit tests alone do not prove safety or profitability.

**No existing defect should be represented as fixed without a committed patch and a verified test result.**
