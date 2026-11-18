# Phase 2: guarded paper ledger (work in progress)

The `PaperDesk` class is an **in-memory, single-process research prototype**. `PersistentPaperDesk` wraps it in a file-backed SQLite transactional snapshot and append-only (but not tamper-proof) event log. It is not connected to a broker, exchange, market-data feed, or strategy simulator.

## Implemented
- BTC/USD and ETH/USD long-only entries, with deterministic `gateway.authorize` on every entry
- Cash balance and marked equity derived from recorded holdings, rather than strategy-supplied P&L
- Risk amount derived from quantity and explicit stop distance; combined open risk checked
- Internal realized P&L on explicit synthetic exits
- Kill switch blocks new entries; daily baseline reset preserves positions
- Fail-closed behavior when price marks are missing or entry prices disagree with marks

## Not implemented — blockers
- No trusted market-data timestamps, freshness verifier, or authenticated strategy authorization
- SQLite now persists snapshots, event history, positions and kill switch across restarts, but events are not tamper-evident and recovery has not been independently crash-tested
- No broker/order reconciliation, pending-order accounting, idempotency, partial fills, fees, or concurrency protection
- No automatic stop execution, gaps/slippage modeling, or guarantee that stop-defined losses are bounded
- No automated UTC-day boundary detection; caller explicitly resets baseline
- No connection between research `simulate` / `backtest` and this ledger

**Do not deploy unattended or connect to live funds.** A passing unit suite only confirms the covered software behavior; it does not establish market safety or profitable trading.
