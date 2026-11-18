# Research evaluation policy

**Do not declare profitability based on an in-sample result.**

## Minimum research outputs
- Data source, instrument, venue, timestamp granularity, timezone and immutable SHA-256 fingerprint
- Strategy family, parameters, train/test periods, experiment ID, source revision
- Gross return, estimated commissions, spread and slippage, **net return**
- Drawdown, volatility, sample size, trade count, benchmark and turnover
- Walk-forward results, holdout performance, sensitivity to costs and parameters
- Explicit caveats for simplified fill assumptions and missing real-world execution effects

## Current implementation
`metrics.py` computes nonannualized period-level volatility, return, and drawdown from supplied equity observations. `validation.py` creates deterministic rolling train/test windows with an optional embargo gap. `audit.py` creates local research records with a data fingerprint. These modules are **building blocks**, not yet integrated into a production backtester, strategy optimizer, or broker execution system.

The existing SMA baseline uses simplified fills. Positions can remain open across UTC midnight, with final-bar liquidation only for finite-backtest accounting. It must not be connected to live execution. There are no real-data performance results yet.

## Promotion gates (to implement)
1. Reproducible dataset and strategy specification.
2. No look-ahead or label leakage.
3. Positive estimated net expectancy on multiple unseen periods.
4. Acceptable tail risk and stress-tested cost sensitivity.
5. Verified risk gateway, execution simulation, and paper fills.
6. Independent performance audit before deployment.

No single metric, including Sharpe, is sufficient for approval.
