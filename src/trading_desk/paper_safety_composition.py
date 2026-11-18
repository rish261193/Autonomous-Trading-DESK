"""Owner-side composition of paper market-data safety controls.

Construct in the ledger owner process, never in a strategy agent. The caller
must supply TWO independently operated, exchange-timestamped quote sources.
This module intentionally does not claim the Kraken ticker's receipt timestamp
is an authenticated exchange event time.
"""
from __future__ import annotations

from .corroborated_prices import CorroboratedPriceSource
from .market_data_breaker import MarketDataCircuitBreaker
from .trusted_paper_intents import TrustedPaperIntentService


def build_guarded_paper_service(desk, *, approved_strategies,
                                primary_source, secondary_source,
                                failure_threshold=3):
    corroborated = CorroboratedPriceSource(
        primary_source, secondary_source, clock=desk.now)
    guarded = MarketDataCircuitBreaker(
        corroborated, failure_threshold=failure_threshold, on_halt=desk.halt)
    return TrustedPaperIntentService(
        desk, approved_strategies=approved_strategies, price_source=guarded)
