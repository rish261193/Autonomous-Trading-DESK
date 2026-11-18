"""Reproducible, dependency-free research baseline. No live orders or claims of profitability."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from itertools import product
from math import isfinite
from typing import Sequence
import csv
import json

@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    close: float

@dataclass(frozen=True)
class Costs:
    fee_bps: float = 10.0
    slippage_bps: float = 5.0

@dataclass(frozen=True)
class Experiment:
    fast: int
    slow: int
    net_return_pct: float
    max_drawdown_pct: float
    trades: int
    ending_equity: float

def load_csv(path: str) -> list[Bar]:
    """CSV columns timestamp (ISO 8601 with timezone), close (positive)."""
    result = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ts = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            if ts.tzinfo is None:
                raise ValueError("timestamps must include timezone")
            price = float(row["close"])
            if not isfinite(price) or price <= 0:
                raise ValueError("close must be positive and finite")
            result.append(Bar(ts.astimezone(timezone.utc), price))
    validate_bars(result)
    return result

def validate_bars(bars: Sequence[Bar]) -> None:
    if len(bars) < 3:
        raise ValueError("at least three bars required")
    previous = None
    for bar in bars:
        if bar.timestamp.tzinfo is None or not isfinite(bar.close) or bar.close <= 0:
            raise ValueError("invalid timestamp or close")
        if previous is not None and bar.timestamp <= previous:
            raise ValueError("bars must be strictly time ordered")
        previous = bar.timestamp

def _signal(closes: Sequence[float], fast: int, slow: int) -> bool:
    return sum(closes[-fast:]) / fast > sum(closes[-slow:]) / slow

def backtest(bars: Sequence[Bar], fast: int, slow: int, costs: Costs = Costs(),
             initial_equity: float = 500.0) -> Experiment:
    """Long-only SMA baseline. Signal from prior close; fill at next bar close.

    Close-to-close fills are a simplified model, NOT realistic intrabar execution.
    No shorting, no leverage. Positions may cross UTC midnight; liquidation
    at the final available bar is solely a finite backtest accounting convention.
    This research baseline does NOT implement stop losses or the risk gateway.
    """
    validate_bars(bars)
    if (not isinstance(fast, int) or isinstance(fast, bool) or
        not isinstance(slow, int) or isinstance(slow, bool) or
        not 1 <= fast < slow < len(bars)):
        raise ValueError("require 1 <= fast < slow < bar count")
    if initial_equity <= 0 or costs.fee_bps < 0 or costs.slippage_bps < 0:
        raise ValueError("invalid capital or costs")
    cash, units, trades = float(initial_equity), 0.0, 0
    peak, max_dd = cash, 0.0
    charge = (costs.fee_bps + costs.slippage_bps) / 10000.0
    for i in range(slow, len(bars)):
        price = bars[i].close
        # Only close at the final bar for finite-backtest accounting.
        if units and i == len(bars)-1:
            cash += units * price * (1 - charge)
            units = 0.0
            trades += 1
        if i != len(bars)-1:
            desired_long = _signal([b.close for b in bars[i-slow:i]], fast, slow)
            if desired_long and not units:
                units = cash / (price * (1 + charge))
                cash = 0.0
                trades += 1
            elif not desired_long and units:
                cash += units * price * (1 - charge)
                units = 0.0
                trades += 1
        equity = cash + units * price
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
    return Experiment(fast, slow, 100 * (cash / initial_equity - 1),
                      100 * max_dd, trades, cash)

def grid_search(bars: Sequence[Bar], fast_values: Sequence[int],
                slow_values: Sequence[int], costs: Costs = Costs()) -> list[Experiment]:
    results = []
    for fast, slow in product(fast_values, slow_values):
        if 1 <= fast < slow < len(bars):
            results.append(backtest(bars, fast, slow, costs))
    return sorted(results, key=lambda x: x.net_return_pct, reverse=True)

def walk_forward(bars: Sequence[Bar], fast_values: Sequence[int],
                 slow_values: Sequence[int], train_fraction: float = 0.7,
                 costs: Costs = Costs()) -> dict:
    """One holdout split. Never rank parameters on holdout performance."""
    validate_bars(bars)
    if not 0.5 <= train_fraction <= 0.9:
        raise ValueError("train_fraction must be between 0.5 and 0.9")
    cut = int(len(bars) * train_fraction)
    train = bars[:cut]
    ranked = grid_search(train, fast_values, slow_values, costs)
    if not ranked:
        raise ValueError("no valid strategy configurations")
    winner = ranked[0]
    # Include historical warmup bars but start simulated execution only on holdout:
    warmup = winner.slow
    test = bars[cut-warmup:]
    # backtest starts at index slow, which is exactly the holdout boundary.
    out = backtest(test, winner.fast, winner.slow, costs)
    return {"selected_on_training_only": asdict(winner),
            "untouched_holdout": asdict(out),
            "train_bars": cut, "holdout_bars": len(bars)-cut,
            "caveat": "Research baseline only; no intrabar fills, stop losses, liquidity, or statistical significance assessment."}

def save_report(report: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
