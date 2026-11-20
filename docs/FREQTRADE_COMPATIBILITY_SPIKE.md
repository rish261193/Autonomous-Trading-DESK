# Freqtrade compatibility spike (paper-only; not integrated)

Status: **preflight and offline tests only**. No Freqtrade dependency installed, no engine launched, no strategy connected, no orders submitted, and no claim of validated execution. Keep `main` unchanged.

## Why this spike

Freqtrade already supports dry-run order simulation, trade persistence, stop-loss callbacks, exchange metadata and backtesting. Reuse these rather than continuing to grow a custom paper execution engine if integration passes. Freqtrade's `confirm_trade_entry` can veto an entry but a strategy callback alone is **not** a secure external authorization boundary; a separately isolated owner must control strategy configuration, credentials, processes and execution permissions.

Sources:
- https://www.freqtrade.io/en/stable/configuration/
- https://www.freqtrade.io/en/stable/strategy-callbacks/
- https://www.freqtrade.io/en/stable/strategy-101/
- https://www.freqtrade.io/en/stable/faq/

## Guardrails

`trading_desk.freqtrade_spike.validate_freqtrade_paper_config` rejects non-dry-run, non-spot, non-USD, non-$500 wallet, additional pairs, non-Kraken exchange, credentials, dynamic pairlists, margin, force entries, enabled API server and excessive concurrent trades. This **does not** secure runtime configuration after validation, nor enforce our 1% per-trade or 3% daily risk policy. Those must be checked independently at execution time.

## Integration acceptance tests (NOT YET PASSED)

1. Pin and install a reviewed Freqtrade version in an isolated environment. Confirm Python/platform support and upstream license obligations before redistribution.
2. Run the preflight against the exact config passed to the engine, then test whether Freqtrade accepts it. Never assume the preflight means engine compatibility.
3. Execute an offline fixture or local dry-run for BTC/USD and ETH/USD only, using $500 paper capital; no exchange credentials.
4. Verify exchange precision, minimum notional, fees, spread, slippage, stop behavior, restart reconciliation, and zero live orders.
5. Verify owner-only signed, short-lived order authorization at the actual execution boundary, with replay protection surviving restart. Prove unapproved strategies and direct API paths cannot create entries.
6. Prove a persistent halt blocks entries but permits independent, trusted stop monitoring and exit management.
7. Compare ledger balances and net P&L against the existing paper engine on identical fixtures; reject unexplained differences.
8. Measure custom code removed and operating cost. Migrate only if demonstrably safer and simpler.

## Compatibility risks

- Freqtrade normally operates one open position per pair; our reservation model can represent more than one. This is a behavioral mismatch, not a drop-in replacement.
- Backtests assume fills under different rules than dry-run execution; neither demonstrates a profitable edge.
- Freqtrade dry-run simulates exchange fills, but this alone does not satisfy independent authenticated price corroboration.
- The proposed runtime engine must remain **behind** an isolated, deterministic risk gateway; never treat Freqtrade strategy callbacks as the sole risk barrier.
- No unattended paper deployment until the independent audit blockers are resolved.
