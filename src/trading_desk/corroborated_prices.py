"""Fail-closed market-data cross-check for paper trading.

Both independent sources must report recent, symbol-matched observations.
No order is approved if sources disagree beyond configured tolerance. This
cannot protect against correlated feed failures or compromised source owners.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from threading import Lock

from .paper_controller import PriceObservation


class CorroboratedPriceSource:
    def __init__(self, primary, secondary, *, clock,
                 max_age_seconds=15, max_deviation_fraction=0.005):
        if not callable(primary) or not callable(secondary) or not callable(clock):
            raise ValueError("Independent sources and trusted clock required")
        if type(max_age_seconds) is not int or not 0 < max_age_seconds <= 60:
            raise ValueError("Invalid quote age policy")
        if (type(max_deviation_fraction) not in (float, int) or
                not isfinite(max_deviation_fraction) or
                not 0 < max_deviation_fraction <= 0.05):
            raise ValueError("Invalid deviation policy")
        self._primary = primary
        self._secondary = secondary
        self._clock = clock
        self._age = max_age_seconds
        self._deviation = max_deviation_fraction
        self._lock = Lock()
        self._last_timestamp = {}

    def _validate(self, observation, symbol, now):
        if (not isinstance(observation, PriceObservation) or
                observation.symbol != symbol or
                type(observation.price) not in (float, int) or
                not isfinite(observation.price) or observation.price <= 0 or
                not isinstance(observation.timestamp, datetime) or
                observation.timestamp.tzinfo is None or
                observation.timestamp.utcoffset() is None):
            raise ValueError("Invalid quote")
        stamp = observation.timestamp.astimezone(timezone.utc)
        age = (now - stamp).total_seconds()
        if not 0 <= age <= self._age:
            raise ValueError("Stale or future quote")
        return stamp

    def __call__(self, symbol):
        if symbol not in {"BTC/USD", "ETH/USD"}:
            raise ValueError("Unsupported symbol")
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("Invalid trusted clock")
        now = now.astimezone(timezone.utc)
        first = self._primary(symbol)
        second = self._secondary(symbol)
        t1 = self._validate(first, symbol, now)
        t2 = self._validate(second, symbol, now)
        deviation = abs(first.price - second.price) / min(first.price, second.price)
        if deviation > self._deviation:
            raise ValueError("Independent prices disagree")
        with self._lock:
            if (t1 < self._last_timestamp.get((symbol, "primary"), t1) or
                    t2 < self._last_timestamp.get((symbol, "secondary"), t2)):
                raise ValueError("Regressed feed timestamp")
            self._last_timestamp[(symbol, "primary")] = t1
            self._last_timestamp[(symbol, "secondary")] = t2
        return first
