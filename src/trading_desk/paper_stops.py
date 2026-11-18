"""Deterministic paper stop monitor: explicit mark, synthetic stop exit only.

Stop orders are not guaranteed fills. A gap below stop executes at the observed
mark, potentially losing more than the planned risk amount.
"""
from __future__ import annotations

from dataclasses import dataclass

from .paper_controller import GuardedPaperController, PriceObservation


@dataclass(frozen=True)
class StopResult:
    triggered: int
    realized_pnl_usd: float


def process_stop_observation(controller: GuardedPaperController,
                             observation: PriceObservation, *, now=None) -> StopResult:
    """Apply fresh marks and close stopped positions at observed paper price."""
    if not controller.valid_observation(observation, now=now):
        raise ValueError("Untrusted or stale stop observation")
    count, pnl = controller.desk.apply_stop_mark(observation.symbol, observation.price)
    return StopResult(count, pnl)
