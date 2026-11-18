# 11 — Integration contract: backend ↔ agent orchestration

**Goal:** make the trust boundary structural. Agents and strategies run in an *untrusted* process and talk to the *trusted* ledger service only through this contract. They never import `trading_desk.pending_orders` or `persistent_paper`, and never open the database.

Status: **proposed.** The audit branch implements the ledger-side primitives this contract relies on (trusted clock, attribution, `close_position`, hash-chained events, `verify_integrity`, `ledger_head`, halt flag). The service wrapper itself is roadmap item B4.

## Principles

1. **Intents, not permissions.** Callers describe what they want. The service decides whether it's allowed. No boolean authorization or freshness fields exist in the API.
2. **The service owns price, time and strategy approval.** Prices come from its market-data adapter, time from its clock, and approval from its persisted registry. Caller-supplied values are hints at most.
3. **Idempotency.** Every mutating request carries a client-generated `idempotency_key`. Replays return the original result.
4. **Typed outcomes.** Every response is `accepted`, `rejected` (stable reason code) or `unavailable` (retry-after). The service never returns a bare exception (fixes F-14).
5. **Read-only by default.** Only the signal engine (trusted, deterministic) may submit intents. LLM components get read endpoints, plus `request_halt` for the Communicator.

## Endpoints (transport-agnostic; HTTP + JSON over a Unix socket suggested)

### `POST /intents` (signal engine only)
```json
{
  "idempotency_key": "2026-11-18T14:00:00Z-momentum-v3-BTC",
  "strategy_id": "momentum",
  "strategy_version": 3,
  "symbol": "BTC/USD",
  "side": "buy",
  "stop_price": 95.0,
  "risk_usd": 4.5,
  "limit_tolerance_bps": 10,
  "ttl_seconds": 60
}
```
The service computes quantity from `risk_usd` and the distance from its current trusted mark to the stop, and checks the strategy registry, freshness, gateway limits, concentration and cost headroom.

Response (illustrative: trusted mark 100, stop 95, so quantity = 4.5 / 5; fee reserve assumes 0.25% taker):
```json
{"outcome": "accepted", "order_id": "o-000123", "fill_reference_price": 100.0, "quantity": 0.9,
 "reserved_notional_usd": 90.0, "reserved_risk_usd": 4.5, "reserved_fee_usd": 0.23,
 "expires_at": "2026-11-18T14:01:00Z", "ledger_seq": 812}
```
or `{"outcome": "rejected", "reason": "DAILY_LOSS_THRESHOLD"}` / `{"outcome": "unavailable", "retry_after_ms": 500}`.

### `POST /orders/{order_id}/cancel` (signal engine)
### `POST /positions/{order_id}/close` (signal engine): the exit price is the trusted mark
### `POST /halt` (signal engine, watchdog, Communicator with an authenticated operator)
Always accepted if the flag can be written; never requires the DB.
### `GET /state`
Cash, equity, day-start equity, open positions (with `strategy_id`, `order_id`, mark age), pending reservations, kill switch, limits in force.
### `GET /events?after_seq=N`
Hash-chained events (`seq`, `kind`, `payload`, `created_at_utc`, `hash`) for the auditor.
### `GET /integrity`
`verify_integrity()` result and `ledger_head()`.

## Rejection reason codes (stable)

`KILL_SWITCH`, `HALT_REQUESTED`, `STRATEGY_NOT_APPROVED`, `STRATEGY_VERSION_RETIRED`, `MARKET_DATA_STALE`, `PRICE_IMPLAUSIBLE`, `UNKNOWN_SYMBOL`, `SHORT_NOT_ALLOWED`, `RISK_LIMIT`, `DAILY_LOSS_THRESHOLD`, `INSUFFICIENT_CASH`, `CONCENTRATION_LIMIT`, `BELOW_MIN_ORDER`, `DUPLICATE_IDEMPOTENCY_KEY` (returns the original), `RESERVATION_EXPIRED`, `INTEGRITY_FAILURE`.

## Event types emitted to orchestration (read-only)

`mark`, `reserve`, `fill`, `cancel`, `close`, `stop_mark`, `daily_reset`, `halt`, plus proposed `reservation_expired`, `watchdog_alert`. These are ledger facts. The `agent_contracts.EventType` messages remain *proposals* between agents and must never be treated as permission to trade.

## Strategy registry (trusted, human-approved)

| Field | Purpose |
|---|---|
| `strategy_id`, `version` | Identity; immutable once approved |
| `spec_sha256` | Hash of the exact code/config |
| `evidence_pack_sha256` | Hash of the `04` validation report |
| `approved_by`, `approved_at_utc` | Human approval |
| `max_risk_usd_per_trade`, `max_notional_usd` | Per-strategy caps (≤ global limits) |
| `status` | `approved` / `paused` / `retired` |

Agents may *propose* a registry entry by producing a spec and evidence pack. Only the owner approves.

## Compatibility with the current library API

| Library call (audit branch) | Contract mapping |
|---|---|
| `GuardedPaperController.reserve/fill` | `POST /intents` (reserve + fill-at-mark collapsed) |
| `PersistentPaperDesk.close_position` | `POST /positions/{order_id}/close` |
| `PersistentPaperDesk.halt`, `halt_requested` | `POST /halt` |
| `snapshot`, `verify_integrity`, `ledger_head` | `GET /state`, `GET /integrity` |
| `PendingOrders.*` with boolean flags | **Not exposed.** Internal only. |
