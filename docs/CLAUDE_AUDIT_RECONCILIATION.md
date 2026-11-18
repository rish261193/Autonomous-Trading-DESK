# Claude audit reconciliation — 2026-11-18

Source: `audit/independent-full-system-review/docs/independent-audit/03_CODE_AND_SECURITY_FINDINGS.md` (audited `main` at `53e0870`). Comparison: `feature/reuse-ccxt-validation` vs `audit/independent-full-system-review`. These branches diverge; do not merge blindly.

## Already implemented independently / overlapping
- F-03 atomic stops: Claude's audit branch fixes this in the persistent ledger's mark path. Our feature branch instead calls `apply_stop_mark` in the controller's observe path. **Prefer Claude's lower-level enforcement**, subject to integration tests, since direct ledger marks should not bypass stops.
- F-06 trusted clock: Claude's audit branch injects a trusted clock and enforces a 120-second skew bound. Our feature branch only rejects naive datetimes. **Prefer Claude's stronger guard**, preserving deterministic test clock injection.
- F-07 ledger integrity: Claude's audit branch adds hash-chained, timestamped events and replay reconciliation. Our feature branch does not have equivalent protection. **Port Claude's implementation and tests**.
- F-08 stable position identity: Claude adds order and strategy attribution and close-by-order-id. **Port**.
- F-10 halt under database contention: Claude adds an out-of-band halt flag. **Port**, then test lock and restart behavior.
- F-12 agent event producer spoofing: Claude hardens orchestrator. **Port**.

## Still open even on Claude's branch
- F-01 caller-supplied authorization booleans / missing process boundary.
- F-02 forged market observations / missing trusted feed ownership.
- F-04 fees, spread, slippage, partial fills and venue minimums.
- F-05 risk limits do not bound gap losses; no automatic halt or concentration cap.
- F-09 exact-price fills and non-expiring reservations.
- F-11 stale-data watchdog and timestamped marks.
- F-13 research-execution model mismatch.
- F-14 typed failure contract.
- F-15 duplicated risk logic / float accounting.
- F-16 documentation drift.
- F-17 CI / supply-chain hardening.
- F-07 and F-10 retain residual risks explicitly described in Claude's audit.

## Safe integration sequence
1. Preserve both branches and their tests. Never merge to main without approval.
2. Integrate Claude's clock, ledger event/replay, stable position IDs, stop handling, halt flag, and producer checks on a separate integration branch; resolve overlapping controller and test behavior explicitly.
3. Run both test suites, adversarial probes, restart/fault tests, and Kraken public-data validation; audit new failures before claiming resolution.
4. Implement the untrusted-agent-to-trusted-ledger service boundary and authenticated market-data ownership; this is **proposed** in Claude's `11_INTEGRATION_CONTRACT.md`, not implemented.
5. Add execution economics and end-to-end strategy parity; rerun the independent audit.

This document is a code-review reconciliation, not a claim that integration or release gates have passed.
