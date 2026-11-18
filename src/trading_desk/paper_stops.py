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
                             observation: PriceObservation, *, now) -> StopResult:
    """Apply fresh marks and close stopped positions at observed paper price."""
    if not controller.observe(observation, now=now):
        raise ValueError("Untrusted or stale stop observation")
    triggered = 0
    pnl = 0.0
    # Re-read each time; position indices change after a close.
    while True:
        desk = controller.desk.snapshot()
        index = next((i for i, position in enumerate(desk.positions)
                      if position.symbol == observation.symbol and
                      observation.price <= position.stop_price), None)
        if index is None:
            break
        pnl += controller.desk.close(index, observation.price)
        triggered += 1
    return StopResult(triggered, pnl)
