"""Explicit, reproducible strategy hypotheses; research only.

No agent calls, broker connectivity, or claims of profitability.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from typing import Iterable


@dataclass(frozen=True)
class StrategySpec:
    family: str
    parameters: tuple[tuple[str, int], ...]
    version: int = 1

    @property
    def identifier(self) -> str:
        params = "-".join(f"{key}{value}" for key, value in self.parameters)
        return f"{self.family}-v{self.version}-{params}"


def sma_hypotheses(fast_windows: Iterable[int], slow_windows: Iterable[int]) -> list[StrategySpec]:
    """Generate parameterized long-only SMA hypotheses, excluding invalid windows."""
    candidates = []
    for fast, slow in product(fast_windows, slow_windows):
        if isinstance(fast, bool) or isinstance(slow, bool) or not isinstance(fast, int) or not isinstance(slow, int):
            raise ValueError("Window lengths must be integers")
        if 1 <= fast < slow:
            candidates.append(StrategySpec("sma_long", (("fast", fast), ("slow", slow))))
    return sorted(set(candidates), key=lambda s: s.identifier)


def validate_strategy(spec: StrategySpec) -> None:
    if spec.version < 1:
        raise ValueError("Strategy version must be positive")
    if spec.family != "sma_long":
        raise ValueError("Strategy family not implemented")
    params = dict(spec.parameters)
    if len(params) != 2 or set(params) != {"fast", "slow"}:
        raise ValueError("SMA requires fast and slow parameters")
    if not all(isinstance(x, int) and not isinstance(x, bool) for x in params.values()):
        raise ValueError("SMA parameters must be integers")
    if not 1 <= params["fast"] < params["slow"]:
        raise ValueError("SMA windows must satisfy 1 <= fast < slow")
