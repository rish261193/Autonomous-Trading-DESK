"""Cost-aware, research-only long/cash strategy comparison with train/holdout split.

Signals are computed using only preceding closes and hypothetically filled at
the current close. This close-fill assumption is optimistic; not executable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Sequence

from .research import Bar, Costs, validate_bars


@dataclass(frozen=True)
class StrategyResult:
    strategy: str
    lookback: int
    net_return_pct: float
    max_drawdown_pct: float
    transactions: int
    ending_equity: float


def _want_long(prior: Sequence[float], lookback: int, strategy: str) -> bool:
    avg = sum(prior[-lookback:]) / lookback
    if strategy == "momentum":
        return prior[-1] > avg
    if strategy == "mean_reversion":
        return prior[-1] < avg
    raise ValueError("unsupported strategy")


def simulate(bars: Sequence[Bar], *, strategy: str, lookback: int,
             costs: Costs = Costs(), initial_equity: float = 500,
             start_index: int | None = None) -> StrategyResult:
    validate_bars(bars)
    if strategy not in {"momentum", "mean_reversion", "buy_hold", "cash"}:
        raise ValueError("unsupported strategy")
    if not isinstance(lookback, int) or isinstance(lookback, bool) or not 2 <= lookback < len(bars):
        raise ValueError("invalid lookback")
    if not isfinite(initial_equity) or initial_equity <= 0:
        raise ValueError("invalid equity")
    if not all(isfinite(v) and v >= 0 for v in (costs.fee_bps, costs.slippage_bps)):
        raise ValueError("invalid costs")
    charge = (costs.fee_bps + costs.slippage_bps) / 10000
    if charge >= 1:
        raise ValueError("costs exceed trade value")
    start = lookback if start_index is None else start_index
    if not isinstance(start, int) or isinstance(start, bool) or not lookback <= start < len(bars) - 1:
        raise ValueError("invalid start index")
    cash, units, transactions = float(initial_equity), 0.0, 0
    peak, max_dd = cash, 0.0
    for i in range(start, len(bars)):
        price = bars[i].close
        # Current bar's price is NOT used for the signal.
        prior = [b.close for b in bars[i - lookback:i]]
        desired = (strategy == "buy_hold" or
                   (strategy != "cash" and _want_long(prior, lookback, strategy)))
        if i == len(bars) - 1:
            desired = False  # finite experiment liquidation, not a daily reset
        if desired and units == 0:
            units = cash / (price * (1 + charge))
            cash = 0.0
            transactions += 1
        elif not desired and units:
            cash += units * price * (1 - charge)
            units = 0.0
            transactions += 1
        equity = cash + units * price
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
    return StrategyResult(strategy, lookback, 100 * (cash / initial_equity - 1),
                          100 * max_dd, transactions, cash)


def compare_holdout(bars: Sequence[Bar], *, lookbacks: Sequence[int] = (6, 12, 24),
                    train_fraction: float = .7, costs: Costs = Costs()) -> dict:
    """Select ONE strategy+lookback on training data; never optimize holdout."""
    validate_bars(bars)
    if not isfinite(train_fraction) or not .5 <= train_fraction <= .9:
        raise ValueError("invalid train fraction")
    cut = int(len(bars) * train_fraction)
    if cut >= len(bars) - 1:
        raise ValueError("insufficient holdout")
    if not lookbacks or any(not isinstance(k, int) or isinstance(k, bool) or k < 2 or k >= cut - 1 for k in lookbacks):
        raise ValueError("invalid lookbacks")
    candidates = [simulate(bars[:cut], strategy=name, lookback=k, costs=costs)
                  for name in ("momentum", "mean_reversion") for k in lookbacks]
    # Deterministic tie-breaking and training-only selection.
    winner = max(candidates, key=lambda x: (x.net_return_pct, -x.max_drawdown_pct,
                                             -x.transactions, x.strategy, -x.lookback))
    selected = simulate(bars, strategy=winner.strategy, lookback=winner.lookback,
                        costs=costs, start_index=cut)
    baselines = {name: asdict(simulate(bars, strategy=name, lookback=winner.lookback,
                                      costs=costs, start_index=cut))
                 for name in ("buy_hold", "cash")}
    return {
        "status": "unverified_research",
        "train_bars": cut,
        "holdout_bars": len(bars) - cut,
        "selected_on_training": asdict(winner),
        "holdout_selected": asdict(selected),
        "holdout_baselines": baselines,
        "costs": asdict(costs),
        "caveats": [
            "Close-to-close fills are hypothetical and may overstate achievable returns.",
            "No risk gateway, stops, order book, liquidity, or actual fills.",
            "Single chronological holdout is not statistical proof of edge.",
            "Training performance selects the model; holdout does not influence selection.",
        ],
    }
