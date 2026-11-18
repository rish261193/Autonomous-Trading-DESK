# Paper intent boundary — implementation status

The paper-only `TrustedPaperIntentService` accepts `PaperBuyIntent` objects, reads prices from a service-owned adapter, checks the approved strategy registry, and passes orders through the existing guarded controller. `paper_intent_http` exposes **reservation only** at `POST /v1/paper/intents`; it does **not** expose a fill endpoint, real exchange execution, risk override, or broker credentials. This is not yet a runnable production deployment or a complete automated trade lifecycle.

## Deployment security requirement

The strategy worker and paper service MUST run under separate OS identities or isolated containers, with the SQLite database and halt file writable only by the service identity. Do not mount the service database into the strategy container. The HTTP API binds only to `127.0.0.1` and now requires a shared-secret HMAC signature over the exact body, timestamp and nonce (30-second clock window, 60-second in-memory replay cache). Generate and distribute a unique 32-byte-or-longer random secret through a restricted secret mount, never source control. **Loopback and HMAC alone are not OS isolation.** The replay cache is not durable across restarts and multiple service replicas cannot share it. A future deployment should use permission-restricted Unix-domain sockets with peer credentials or a hardened authenticated service network, along with separate OS identities and database ACLs. Do not expose port 8765 to the internet. The service's strategy allowlist is not a cryptographic identity proof.

## Price-source limitations

`KrakenPublicPriceSource` calls the unauthenticated public ticker endpoint for BTC/USD and ETH/USD, rejects malformed and mismatched responses, and timestamps at receipt. Kraken's Ticker response does not provide an exchange event timestamp. Therefore receipt time **does not prove quote freshness**; it also cannot detect plausible but manipulated or outlier prices. Add exchange-timestamped market data, independent corroboration, outlier limits and a stale-data watchdog before calling F-02 closed.

## Remaining blockers

- F-01: HMAC request authentication is implemented; process separation, durable replay protection, database access control and adversarial deployment tests remain open.
- F-02: independent price provenance, stale-event checks and plausibility checks remain open.
- F-04/F-09: execution fees, slippage, minimum order sizes, partial fills and reservation expiry remain open.
- The HTTP API currently reserves only; a controlled fill workflow remains to be designed and tested.
- CI green verifies unit tests, not production security or profitability.
- No live trading; `main` unchanged.

## Independent quote validator (not yet wired into deployment)

`CorroboratedPriceSource` accepts two separately configured source adapters and fails closed on mismatched symbols, stale/future timestamps, disagreement beyond 0.5% by default, feed errors and regressed timestamps. It is a reusable validator, **not** a live secondary exchange integration. The current Kraken Ticker adapter uses local receipt time rather than exchange event time; wiring two receipt-timestamped ticker sources would not meet F-02's exchange-timestamp provenance requirement. A future deployment must supply independently sourced, exchange-timestamped events and test disconnect recovery and persisted monotonic sequence checks.

## Market-data circuit breaker (new, not yet deployed)

`MarketDataCircuitBreaker` wraps a source and halts future source calls after three consecutive exceptions by default; an owner-only method resets it. When used as the `TrustedPaperIntentService` price source, failed observations reject new reservations and fills. This is an **in-memory source-level halt**, not the persistent ledger kill switch: process restarts clear its state, and it does not automatically call `PersistentPaperDesk.halt()`. Deployment must persist the halt, test watchdog behavior during idle periods, and ensure existing position management remains safe during feed loss. Do not expose reset through the strategy HTTP API.

## Owner-side composition and persistent kill switch

`build_guarded_paper_service` now connects two-source corroboration to the feed circuit breaker and the persistent desk's `halt()` callback. Repeated source errors trip the breaker and write the ledger `.HALT` flag before attempting the SQLite kill-switch update; restart reconciliation honors that flag. Unit tests exercise feed outage → denied intents → persistent halt → restart. This is not a deployed service, and a missing feed heartbeat when no requests occur is **not** detected. The owner must run an independent watchdog and isolate the database from agents. `reset_by_owner()` resets only the in-memory feed counter, never the persistent kill switch. CI must pass before these claims are treated as verified.
