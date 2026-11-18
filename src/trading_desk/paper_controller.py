"""Fail-closed paper-trading control plane for trusted inputs.

A caller must explicitly supply an approved strategy registry and UTC-aware
price observations. This module does not authenticate a remote market-data feed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite

from .pending_orders import PendingOrders


@dataclass(frozen=True)
class PriceObservation:
    symbol: str
    price: float
    timestamp: datetime


class GuardedPaperController:
    def __init__(self, persistent_desk, approved_strategies: frozenset[str],
                 max_age_seconds: int = 60):
        if not isinstance(approved_strategies, frozenset) or not all(
                isinstance(s, str) and s.strip() for s in approved_strategies):
            raise ValueError("Explicit strategy allowlist required")
        if type(max_age_seconds) is not int or not 0 < max_age_seconds <= 3600:
            raise ValueError("Invalid freshness policy")
        self.desk = persistent_desk
        self.orders = PendingOrders(persistent_desk)
        self.approved_strategies = approved_strategies
        self.max_age_seconds = max_age_seconds

    def valid_observation(self, observation: PriceObservation, *, now: datetime) -> bool:
        if (not isinstance(observation, PriceObservation) or
                not isinstance(now, datetime) or now.tzinfo is None or
                now.utcoffset() is None or
                not isinstance(observation.timestamp, datetime) or
                observation.timestamp.tzinfo is None or
                observation.timestamp.utcoffset() is None or
                observation.symbol not in {"BTC/USD", "ETH/USD"} or
                type(observation.price) not in (int, float) or
                not isfinite(observation.price) or observation.price <= 0):
            return False
        age = (now.astimezone(timezone.utc) -
               observation.timestamp.astimezone(timezone.utc)).total_seconds()
        if not 0 <= age <= self.max_age_seconds:
            return False
        return True

    def observe(self, observation: PriceObservation, *, now: datetime) -> bool:
        if not self.valid_observation(observation, now=now):
            return False
        # Apply the mark and any triggered stops in the same database transaction.
        # A plain mark here could leave a breached stop open until another worker runs.
        self.desk.apply_stop_mark(observation.symbol, observation.price)
        return True

    def reserve(self, order_id: str, *, strategy_id: str, symbol: str,
                price: float, stop_price: float, quantity: float,
                observation: PriceObservation, now: datetime) -> bool:
        if strategy_id not in self.approved_strategies:
            return False
        if not isinstance(observation, PriceObservation):
            return False
        if observation.symbol != symbol or observation.price != price:
            return False
        if not self.observe(observation, now=now):
            return False
        return self.orders.reserve(
            order_id, strategy_id=strategy_id, symbol=symbol, price=price,
            stop_price=stop_price, quantity=quantity,
            strategy_authorized=True, market_data_fresh=True)

    def cancel(self, order_id: str) -> bool:
        return self.orders.cancel(order_id)

    def fill(self, order_id: str, *, strategy_id: str, observation: PriceObservation,
             now: datetime) -> bool:
        """Require a new fresh observation and currently approved strategy at fill."""
        if strategy_id not in self.approved_strategies:
            return False
        if not self.valid_observation(observation, now=now):
            return False
        # A fill must not silently move the mark; price must match the reservation.
        if self.desk.snapshot().marks.get(observation.symbol) != observation.price:
            return False
        return self.orders.fill(order_id, strategy_authorized=True,
                                market_data_fresh=True,
                                expected_strategy_id=strategy_id,
                                expected_symbol=observation.symbol)
