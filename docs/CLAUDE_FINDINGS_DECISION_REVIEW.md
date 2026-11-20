# Technical decision review of Claude independent audit — 2026-11-18

Basis: Claude's 01, 03, 05, 06, 10 and 11 audit documents, with source inspection of the integrated controller and ledger. This is an architectural decision review, **not** independent execution of every probe or a green CI claim.

| Finding | Decision | Rationale / required evidence |
|---|---|---|
| F-01 self-asserted authorization | **ACCEPT — critical blocker** | Caller booleans are not authentication. Isolate trusted ledger/gateway process, persisted approval registry, intent-only API. Prove bypass cannot reach DB or PendingOrders. |
| F-02 forged marks | **ACCEPT — critical blocker** | Hash-chain proves internal consistency, not exchange authenticity. Own feed adapter and clock in trusted process; provenance, sequence, age and outlier handling. |
| F-03 skipped stops | **ACCEPT existing Claude fix** | Enforce at ledger mark transaction, not only controller. Integration regression covers both paths; run suite. |
| F-04 frictionless fills | **ACCEPT** | Add configurable venue fee, spread, slippage, min notional and precision; test gross/net replay. No arbitrary default fee assumptions. |
| F-05 limits not loss guarantees | **ACCEPT with policy decision** | Preserve existing 1% entry risk and 3% daily threshold; add exposure caps, halt on breach. Do not promise gaps are bounded or automatically flatten without explicit policy. |
| F-06 caller clock | **ACCEPT Claude stronger fix** | Clock injection and bounded caller skew are preferable to naive-time rejection alone; process isolation still necessary. |
| F-07 integrity | **ACCEPT Claude fix, PARTIAL security claim** | Chain + replay detect accidental/partial edits. External anchored head needed for strong tamper evidence. Migration must be tested on existing DB copies. |
| F-08 index identity | **ACCEPT Claude fix** | Stable order IDs and strategy attribution prevent wrong-position exits and permit per-strategy accounting. |
| F-09 exact-price/TTL | **ACCEPT** | Fill at current trusted price with tolerance and revalidate risk; auto-expire reservations with logged cancellation. |
| F-10 halt under DB lock | **ACCEPT Claude partial fix** | Out-of-band halt flag fails closed. Add automatic triggers, operator-only resume and pending-order policy; test races. |
| F-11 stale marks | **ACCEPT** | Timestamped trusted marks and watchdog; owner must set age threshold and outage behavior. |
| F-12 producer spoofing | **ACCEPT Claude fix, limited claim** | Role equality is useful defense in depth but not process authentication; no agent can approve orders. |
| F-13 research mismatch | **ACCEPT — evidence blocker** | Research and ledger must share sizing, stop and execution-cost semantics; compare trade-by-trade fixture replay. |
| F-14 inconsistent errors | **ACCEPT for service API** | Typed accepted/rejected/unavailable responses; retain explicit fail-closed internal exceptions where useful. |
| F-15 duplicated risk/float | **PARTIAL / DEFER** | Consolidate risk formula before adding cost model; do not prematurely rewrite all paper arithmetic to Decimal. Adopt fixed-point/Decimal before broker reconciliation. |
| F-16 documentation drift | **ACCEPT** | Mark superseded audits, distinguish audited baseline from integration state, avoid safety/profitability claims. |
| F-17 CI and supply chain | **ACCEPT with prioritization** | Require CI on integration branch, Python matrix, lint/type checks, SHA-pinned actions and protected main; no release without verification. |

## Recommendations accepted with qualification

- **Prioritize evidence of trading edge before agent expansion:** yes. A zero-edge strategy makes sophisticated orchestration irrelevant. However, trusted-data provenance and realistic execution-cost model are prerequisites to meaningful research; do not postpone all B work until A5.
- **11 roles to 5 components:** directionally sound. Do not delete working modules solely to meet an arbitrary component count. Keep LLMs out of order authorization.
- **≥200 nulls, 12-month holdout, positive expectancy CI and 30-day soak:** useful proposed acceptance criteria, not mathematically universal guarantees. Pre-register strategy and choose statistically defensible thresholds based on data frequency, effective sample size and regime coverage.
- **Cost estimates and venue fee table:** illustrative and date/venue/tier sensitive; verify against the selected exchange before implementation.
- **No automatic flatten on halt without a policy:** a stale feed may make market exits unsafe; halt must block new entries, preserve auditability, and require explicit recovery rules.

## Integration gate

1. Existing Claude changes are the integration branch base, not yet independently re-executed.
2. Preserve feature-branch work and cherry-pick only non-overlapping protections after review.
3. Run full Python 3.11/3.13 suite, adversarial probes, fault/restart tests and public-data validation. Resolve all unexpected failures and expected-failure changes.
4. Enforce trusted process boundary and market-data ownership; then implement fees, reservation TTL, watchdog, exposure policy and research parity.
5. No merge to main, unattended execution or live trading until verified release gates and explicit approval.
