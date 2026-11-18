"""Simplified event-driven research simulator for long-only strategies.

Trades at bar close based on *prior* closes. The simulator does not model
order-book fills, stop orders, or outages. Positions can cross UTC midnight.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Sequence
from .research import Bar, Costs, validate_bars
from .signals import SignalSpec, signal_at, validate_spec
from .metrics import evaluate_equity

@dataclass(frozen=True)
class SimulationResult:
    family: str
    lookback: int
    threshold_bps: float
    net_return_pct: float
    max_drawdown_pct: float
    trades: int
    ending_equity: float
    total_estimated_cost_usd: float

def simulate(bars: Sequence[Bar], spec: SignalSpec, costs: Costs = Costs(),
             initial_equity: float = 500.0) -> SimulationResult:
    validate_bars(bars)
    validate_spec(spec)
    if len(bars) <= spec.lookback + 1:
        raise ValueError("Not enough bars")
    if initial_equity <= 0 or costs.fee_bps < 0 or costs.slippage_bps < 0:
        raise ValueError("Invalid capital or costs")
    import math
    if not all(math.isfinite(v) for v in (initial_equity, costs.fee_bps, costs.slippage_bps)):
        raise ValueError("Non-finite capital or costs")
    cash, units, trades, paid = float(initial_equity), 0.0, 0, 0.0
    charge = (costs.fee_bps + costs.slippage_bps) / 10000
    if charge >= 1:
        raise ValueError("Transaction cost too high")
    closes = [bar.close for bar in bars]
    curve = [cash]
    for i in range(spec.lookback + 1, len(bars)):
        price = closes[i]
        # No UTC midnight liquidation; final-bar exit is accounting only.
        if units and i == len(bars)-1:
            gross = units * price
            fee = gross * charge
            cash += gross - fee
            paid += fee
            units = 0.0
            trades += 1
        if i != len(bars)-1:
            long_signal = signal_at(closes, i, spec)
            if long_signal and not units:
                fee = cash * charge / (1 + charge)
                units = cash / (price * (1 + charge))
                paid += fee
                cash = 0.0
                trades += 1
            elif not long_signal and units:
                gross = units * price
                fee = gross * charge
                cash += gross - fee
                paid += fee
                units = 0.0
                trades += 1
        curve.append(cash + units * price)
    perf = evaluate_equity(curve)
    return SimulationResult(spec.family, spec.lookback, spec.threshold_bps,
                            perf.net_return_pct, perf.max_drawdown_pct,
                            trades, cash, paid)

def screen(bars: Sequence[Bar], specs: Sequence[SignalSpec],
           costs: Costs = Costs()) -> list[SimulationResult]:
    if len(specs) > 10000:
        raise ValueError("Maximum 10000 configurations per batch")
    return sorted((simulate(bars, spec, costs) for spec in specs),
                  key=lambda result: result.net_return_pct, reverse=True)
