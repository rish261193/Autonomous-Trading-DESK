"""Fail-closed circuit breaker for paper market-data acquisition.

After repeated feed failures, require explicit operator reset. No autonomous
agent can reset this breaker through the trade-intent API.
"""
from __future__ import annotations

from threading import Lock
from time import monotonic


class MarketDataHalted(RuntimeError):
    pass


class MarketDataCircuitBreaker:
    def __init__(self, source, *, failure_threshold=3):
        if not callable(source):
            raise ValueError("Price source required")
        if type(failure_threshold) is not int or not 1 <= failure_threshold <= 100:
            raise ValueError("Invalid failure threshold")
        self._source = source
        self._threshold = failure_threshold
        self._failures = 0
        self._halted = False
        self._lock = Lock()

    @property
    def halted(self):
        with self._lock:
            return self._halted

    def __call__(self, symbol):
        # Hold lock during source call: concurrent callers cannot slip through
        # a transition to halted. Owner must configure source timeouts.
        with self._lock:
            if self._halted:
                raise MarketDataHalted("Market-data circuit breaker is halted")
            try:
                quote = self._source(symbol)
                if quote is None:
                    raise ValueError("Missing quote")
            except Exception:
                self._failures += 1
                if self._failures >= self._threshold:
                    self._halted = True
                raise
            self._failures = 0
            return quote

    def reset_by_owner(self):
        """Only the owner process may invoke this; never expose via agent API."""
        with self._lock:
            self._halted = False
            self._failures = 0
