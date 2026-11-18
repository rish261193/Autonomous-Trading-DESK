# Phase 2: guarded paper ledger (work in progress)

The `PaperDesk` class is an **in-memory, single-process research prototype**. `PersistentPaperDesk` wraps it in a file-backed SQLite transactional snapshot and append-only (but not tamper-proof) event log. It is not connected to a broker, exchange, market-data feed, or strategy simulator.

## Implemented
- BTC/USD and ETH/USD long-only entries, with deterministic `gateway.authorize` on every entry
- Cash balance and marked equity derived from recorded holdings, rather than strategy-supplied P&L
- Risk amount derived from quantity and explicit stop distance; combined open risk checked
- Internal realized P&L on explicit synthetic exits
- Kill switch blocks new entries; daily baseline reset preserves positions
- Fail-closed behavior when price marks are missing or entry prices disagree with marks

## Pending-order prototype
- `PendingOrders` adds SQLite-backed unique IDs, reserved cash/risk, cancellations and synthetic fills
- The legacy direct `PersistentPaperDesk.enter()` API still bypasses reservations and must be removed before any deployment
- Pending orders are synthetic, not reconciled against an exchange; no partial fills or broker acknowledgement

## Not implemented — blockers
- No trusted market-data timestamps, freshness verifier, or authenticated strategy authorization
- SQLite now persists snapshots, event history, positions and kill switch across restarts, but events are not tamper-evident and recovery has not been independently crash-tested
- Pending reservations and order-ID idempotency exist, but broker reconciliation, partial fills, fees, and end-to-end enforcement are still missing
- No automatic stop execution, gaps/slippage modeling, or guarantee that stop-defined losses are bounded
- No automated UTC-day boundary detection; caller explicitly resets baseline
- No connection between research `simulate` / `backtest` and this ledger

**Do not deploy unattended or connect to live funds.** A passing unit suite only confirms the covered software behavior; it does not establish market safety or profitable trading.

## Phase 2 implementation freeze / verification backlog (2026-11-18)
Code paths added:
- `persistent_paper.py`: SQLite state and event snapshots, restart recovery, persisted kill switch
- `pending_orders.py`: unique order IDs, cash/risk reservations, cancellation, synthetic fills
- `paper_controller.py`: strategy allowlist and UTC timestamp age checks at reservation
- `paper_stops.py`: observed-price synthetic stops, including gaps below stop
- `PersistentPaperDesk.enter` intentionally disabled to remove one direct-entry bypass

**Phase 2 code coverage is not Phase 2 acceptance.** The existing CI failures are deliberately deferred until the stabilization pass, as requested. Known design and integration gaps to resolve before calling the system safe:
1. `PendingOrders.fill` relies on persisted authorization/freshness booleans; revalidate a new authenticated observation and live allowlist at fill time
2. `PaperDesk.enter` remains publicly callable on standalone in-memory instances; never expose it to untrusted strategy code
3. Stop monitor mark/close operations are not one transaction, and stop evaluation is not wired to a continuous feed
4. The event table is not cryptographically tamper-evident, and there is no snapshot/event consistency verification
5. Pending-order fills do not model fees, partial fills, exchange acknowledgements or outages
6. Daily baseline reset requires an external scheduler and durable UTC-day identifier
7. Current tests and CI must be fixed and verified, including old tests expecting now-disabled direct entry
8. Research simulators are not connected to this risk-enforced execution path

**Release gate: FAIL / NOT READY.** No live trading or unattended deployment.
