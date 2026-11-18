# Autonomous Strategy Research Lab

## Tool-first, agent-directed
Agents identify hypotheses and review evidence; computational tools calculate indicators, screen thousands of parameter configurations, backtest, and optimize.

## Research pipeline
1. Discover candidate ideas from literature, public implementations, and market behavior.
2. Convert each hypothesis into explicit, testable entry/exit rules and assumptions.
3. Assign a strategy family ID, experiment ID, data snapshot, and cost model.
4. Reject infeasible candidates (look-ahead, insufficient liquidity, incompatible spot rules, unbounded risk).
5. Screen parameter combinations using reproducible numerical code.
6. Evaluate on walk-forward and genuinely unseen data; account for multiple testing and overfitting.
7. Stress test fees, spreads, slippage, data outages, and changing market regimes.
8. Version and approve candidates before paper trading.
9. Audit realized paper fills, net P&L, drawdowns, strategy-level attribution, and degradation.
10. Retire or revalidate failing strategies; never let an agent silently change an active strategy.

## Initial constraints
BTC/USD and ETH/USD spot; $500 simulated equity; no leverage or shorts; no overnight positions; max 1% equity risk per trade and 3% daily loss threshold. Define the trading-day boundary before deployment. No arbitrary daily profit target or trade-count ceiling. Costs must be included before declaring a strategy profitable.

## First research milestone
Screen 1,000 **configurations** with reproducible results; distinguish configurations from independent strategy families. A profitable backtest is not proof of a live edge.
