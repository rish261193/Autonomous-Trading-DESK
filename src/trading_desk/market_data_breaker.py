"""Fail-closed paper market-data circuit breaker.

When the threshold is reached, persist the desk kill switch BEFORE returning.
No strategy-facing reset exists. A failed halt persistence operation also
fails closed; operator intervention is required.
"""
from __future__ import annotations

from threading import Lock


class MarketDataHalted(RuntimeError):
    pass


class MarketDataCircuitBreaker:
    def __init__(self, source, *, failure_threshold=3, on_halt=None):
        if not callable(source):
            raise ValueError("Price source required")
        if type(failure_threshold) is not int or not 1 <= failure_threshold <= 100:
            raise ValueError("Invalid failure threshold")
        if on_halt is not None and not callable(on_halt):
            raise ValueError("Halt callback must be callable")
        self._source = source
        self._threshold = failure_threshold
        self._on_halt = on_halt
        self._failures = 0
        self._halted = False
        self._lock = Lock()

    @property
    def halted(self):
        with self._lock:
            return self._halted

    def __call__(self, symbol):
        # Serialize quote calls and halt transitions; source must have a timeout.
        with self._lock:
            if self._halted:
                raise MarketDataHalted("Market-data circuit breaker is halted")
            try:
                quote = self._source(symbol)
                if quote is None:
                    raise ValueError("Missing quote")
            except Exception as source_error:
                self._failures += 1
                if self._failures >= self._threshold:
                    self._halted = True
                    if self._on_halt is not None:
                        try:
                            self._on_halt()
                        except Exception as halt_error:
                            raise MarketDataHalted(
                                "Feed failed and persistent halt could not be confirmed"
                            ) from halt_error
                raise
            self._failures = 0
            return quote

    def reset_by_owner(self):
        """Reset local counter only. NEVER clears a persistent ledger halt."""
        with self._lock:
            self._halted = False
            self._failures = 0
