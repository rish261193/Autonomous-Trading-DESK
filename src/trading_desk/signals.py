"""Causal long/flat strategy signals computed using historical closes only.

Signals at index i are calculated from closes up to i-1. They are intended
for research, not broker execution.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Sequence

@dataclass(frozen=True)
class SignalSpec:
    family: str
    lookback: int
    threshold_bps: float = 0.0

def validate_spec(spec: SignalSpec) -> None:
    if spec.family not in {"momentum", "mean_reversion", "breakout"}:
        raise ValueError("Unknown strategy family")
    if not isinstance(spec.lookback, int) or isinstance(spec.lookback, bool) or spec.lookback < 2:
        raise ValueError("lookback must be an integer >= 2")
    if not isfinite(spec.threshold_bps) or not 0 <= spec.threshold_bps <= 10000:
        raise ValueError("threshold_bps must be finite and between 0 and 10000")

def signal_at(closes: Sequence[float], index: int, spec: SignalSpec) -> bool:
    """Return whether to be long at index, without reading closes[index]."""
    validate_spec(spec)
    if index < spec.lookback + 1 or index > len(closes):
        raise ValueError("Insufficient history or invalid index")
    history = closes[index-spec.lookback:index]
    if any(not isfinite(p) or p <= 0 for p in history):
        raise ValueError("Closes must be positive finite prices")
    last = history[-1]
    threshold = spec.threshold_bps / 10000
    if spec.family == "momentum":
        return last > history[0] * (1 + threshold)
    if spec.family == "mean_reversion":
        average = sum(history) / len(history)
        return last < average * (1 - threshold)
    # Breakout compares prior close to the maximum of earlier closes,
    # explicitly excluding the close that triggers the signal.
    return last > max(history[:-1]) * (1 + threshold)
