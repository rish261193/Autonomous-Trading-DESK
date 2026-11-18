# Historical Data Contract

Input CSV: `timestamp,close`, with ISO 8601 timezone-aware timestamps in strictly ascending order and finite positive closes. UTC normalization is automatic. Use **real market data with provenance**, exchange venue, quote currency, candle interval, timezone, source retrieval date, and missing-bar policy recorded before interpreting results.

## Execution assumptions and limits

The initial SMA strategy uses only prior-bar observations to decide whether to trade at the current bar's close. This simplified fill is not a realistic order-book execution simulation. It assumes no spread variation, price impact, partial fills, outages, funding, taxes, or minimum order sizes. Trading costs are configurable basis-point estimates. UTC date transitions trigger liquidation at the first available bar of the new day, which may be after midnight; therefore the implementation **does not yet guarantee no overnight exposure**. Do not use it to place orders.

A single train/holdout split is a research demonstration, not rigorous walk-forward optimization. The lab must later add purging, repeated rolling validation, benchmark comparisons, execution-aware event simulation, position sizing and independent risk-gateway checks.

Never treat synthetic test data as market performance evidence.
