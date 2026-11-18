"""Pure performance calculations for marked-to-market equity curves."""
from __future__ import annotations
from dataclasses import dataclass
from math import sqrt, isfinite
from typing import Sequence

@dataclass(frozen=True)
class Performance:
    starting_equity: float
    ending_equity: float
    net_return_pct: float
    max_drawdown_pct: float
    volatility_pct_per_period: float | None
    sharpe_per_period: float | None
    observations: int

def evaluate_equity(equity: Sequence[float]) -> Performance:
    if len(equity) < 2:
        raise ValueError("At least two equity observations required")
    if any(not isfinite(x) or x <= 0 for x in equity):
        raise ValueError("Equity must be positive and finite")
    start, end = equity[0], equity[-1]
    peak, max_dd = start, 0.0
    for value in equity:
        peak = max(peak, value)
        max_dd = max(max_dd, 1 - value / peak)
    returns = [equity[i] / equity[i-1] - 1 for i in range(1, len(equity))]
    avg = sum(returns) / len(returns)
    variance = sum((r - avg)**2 for r in returns) / len(returns)
    vol = sqrt(variance)
    # Not annualized. The caller must specify sampling interval and risk-free rate
    # before interpreting this as a conventional Sharpe ratio.
    sharpe = avg / vol if vol > 0 else None
    return Performance(start, end, 100 * (end/start - 1), 100 * max_dd,
                       100 * vol, sharpe, len(equity))
