"""Public Kraken spot ticker adapter for the owner-controlled paper service.

No credentials or trading endpoints. This adapter is a *single-source* feed,
not proof against exchange errors or price outliers. Reject malformed data,
missing timestamps, stale quotes and mismatched instruments.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from urllib.parse import urlencode
from urllib.request import urlopen
import json

from .paper_controller import PriceObservation

_PAIRS = {"BTC/USD": ("XBTUSD", {"XXBTZUSD", "XBTUSD"}),
          "ETH/USD": ("ETHUSD", {"XETHZUSD", "ETHUSD"})}


class KrakenPublicPriceSource:
    def __init__(self, *, timeout_seconds: float = 5.0, opener=urlopen,
                 clock=lambda: datetime.now(timezone.utc)):
        if not 0 < timeout_seconds <= 30:
            raise ValueError("Invalid feed timeout")
        self.timeout_seconds = timeout_seconds
        self.opener = opener
        self.clock = clock

    def __call__(self, symbol: str) -> PriceObservation:
        if symbol not in _PAIRS:
            raise ValueError("Unsupported instrument")
        pair, accepted = _PAIRS[symbol]
        url = "https://api.kraken.com/0/public/Ticker?" + urlencode({"pair": pair})
        with self.opener(url, timeout=self.timeout_seconds) as response:
            payload = json.load(response)
        if not isinstance(payload, dict) or payload.get("error") != []:
            raise ValueError("Kraken API error")
        result = payload.get("result")
        if not isinstance(result, dict) or len(result) != 1:
            raise ValueError("Ambiguous ticker response")
        key, ticker = next(iter(result.items()))
        if key not in accepted or not isinstance(ticker, dict):
            raise ValueError("Unexpected ticker instrument")
        # Last trade price is the public ticker's c[0].
        last = ticker.get("c")
        if not isinstance(last, list) or not last:
            raise ValueError("Missing last trade")
        try:
            price = float(last[0])
        except (ValueError, TypeError, OverflowError):
            raise ValueError("Invalid last trade") from None
        if not isfinite(price) or price <= 0:
            raise ValueError("Invalid last trade")
        # Kraken Ticker has no last-trade timestamp. Receipt time is NOT a
        # verified exchange event time; this limits freshness guarantees.
        observed_at = self.clock()
        if not isinstance(observed_at, datetime) or observed_at.tzinfo is None:
            raise ValueError("Clock must be UTC aware")
        return PriceObservation(symbol, price, observed_at.astimezone(timezone.utc))
