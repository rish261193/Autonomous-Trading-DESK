# Multiple strategy-family research baseline

Implemented as deterministic long/flat signals in `signals.py`:

- **Momentum:** previous close exceeds the close at the start of the lookback window by a configurable threshold.
- **Mean reversion:** previous close is below the lookback average by a configurable threshold.
- **Breakout:** previous close exceeds the maximum of earlier closes in the lookback window.

The `simulator.py` module screens all three with configurable estimated transaction costs and reports equity, drawdown and trading activity. These are deliberately simple hypotheses, **not discovered or validated edges**.

## Critical limitations

The simulator fills at bar close based on prior closes; real execution will differ. It approximates daily liquidation at the first available next-day bar, which can violate the no-overnight requirement. There are no protective stops, independent risk-gateway enforcement, actual exchange constraints, liquidity modelling, market-data provenance, or real-data performance evidence. The `total_estimated_cost_usd` field represents modeled percentage charges on trade notional, not a complete trading cost accounting. Never connect this simulator directly to a broker.

## Next

Integrate the three families into rolling train-only selection and unseen-period evaluation. Add an execution-aware paper simulator and enforce session cutoff before considering live paper orders.
