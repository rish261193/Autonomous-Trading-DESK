"""Paper-only intent boundary (audit F-01/F-02).

Only the owner process may construct this service with its ledger, approved
strategies and trusted market-data adapter. Agents submit intents, not marks,
authorization booleans or clocks. Do not expose ledger/database access to
untrusted processes. This is NOT a network/process isolation implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Callable

from .paper_controller import GuardedPaperController, PriceObservation


@dataclass(frozen=True)
class PaperBuyIntent:
    order_id: str
    strategy_id: str
    symbol: str
    quantity: float
    stop_price: float


class TrustedPaperIntentService:
    """Owner-controlled paper service; no exchange order placement."""

    def __init__(self, desk, *, approved_strategies: frozenset[str],
                 price_source: Callable[[str], PriceObservation],
                 max_age_seconds: int = 60):
        if not callable(price_source):
            raise ValueError("Trusted price source required")
        self._source = price_source
        self._controller = GuardedPaperController(
            desk, approved_strategies, max_age_seconds=max_age_seconds)

    def _observation(self, symbol: str, *, stop_monitoring=False) -> PriceObservation | None:
        try:
            observation = (self._source.observe_for_stops(symbol)
                           if stop_monitoring and hasattr(self._source, 'observe_for_stops')
                           else self._source(symbol))
        except Exception:
            return None  # Feed outages must not authorize an order.
        if not isinstance(observation, PriceObservation):
            return None
        if observation.symbol != symbol:
            return None
        if not self._controller.valid_observation(observation):
            return None
        return observation

    def submit(self, intent: PaperBuyIntent) -> bool:
        if not isinstance(intent, PaperBuyIntent):
            return False
        if (not isinstance(intent.order_id, str) or
                not 0 < len(intent.order_id) <= 128 or
                not isinstance(intent.strategy_id, str) or
                intent.strategy_id not in self._controller.approved_strategies or
                intent.symbol not in {"BTC/USD", "ETH/USD"} or
                not all(type(x) in (int, float) and isfinite(x) and x > 0
                        for x in (intent.quantity, intent.stop_price))):
            return False
        observation = self._observation(intent.symbol)
        if observation is None or intent.stop_price >= observation.price:
            return False
        return self._controller.reserve(
            intent.order_id, strategy_id=intent.strategy_id,
            symbol=intent.symbol, price=observation.price,
            stop_price=intent.stop_price, quantity=intent.quantity,
            observation=observation)

    def fill(self, order_id: str, *, strategy_id: str, symbol: str) -> bool:
        if (not isinstance(order_id, str) or
                strategy_id not in self._controller.approved_strategies or
                symbol not in {"BTC/USD", "ETH/USD"}):
            return False
        observation = self._observation(symbol)
        if observation is None:
            return False
        return self._controller.fill(
            order_id, strategy_id=strategy_id, observation=observation)

    def observe(self, symbol: str) -> bool:
        if symbol not in {"BTC/USD", "ETH/USD"}:
            return False
        observation = self._observation(symbol, stop_monitoring=True)
        return (observation is not None and
                self._controller.observe(observation))
