# Reuse evaluation — first isolated integration

Status: **experimental**. Branch `feature/reuse-ccxt-validation`. No live trading, no merge to main.

## Inspected upstream

- CCXT `ccxt/ccxt`: MIT license; Kraken adapter and exchange abstraction.
- Freqtrade `freqtrade/freqtrade`: GPL-3.0-only; tested backtesting and persistence modules, but no proof of compatibility with our independent risk gateway.
- VectorBT `polakowo/vectorbt`: Commons Clause restrictions; do not embed in commercial service without legal review.
- NautilusTrader `nautechsystems/nautilus_trader`: LGPL-3.0; defer complexity until needed.

These observations do not certify upstream code as free of defects.

## First integration

`trading_desk.ccxt_market_data` is a read-only, optional CCXT Kraken adapter. It retains **full OHLCV** rather than the previous close-only data; excludes incomplete candles; rejects duplicates, invalid values and gaps; persists SHA-256 provenance. It refuses overwrites. It does **not** authorize or place orders.

CCXT is not bundled or vendored; install it separately when running a real exchange fetch. The unit tests use a fake exchange, so they do not establish real Kraken connectivity.

## Limitations and next gates

1. Verify exact CCXT package version, package hash, supported Python versions and current Kraken API behavior; pin the dependency.
2. Obtain a sufficiently long, licensed historical exchange OHLCV dataset for untouched holdout validation. Kraken's recent OHLC endpoint is capped.
3. Compare Freqtrade's backtest and dry-run accounting with our ledger using identical synthetic scenarios, costs, stops, and 1% planned risk. Do not route order execution around the gateway.
4. Review GPL obligations for the planned commercial product.
5. Run CI and verify all existing tests. Only then consider an isolated Freqtrade research sandbox.

No trading edge or unattended paper-trading readiness is claimed.
