"""Phase 3 research-only intelligence; deliberately cannot submit orders."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite


@dataclass(frozen=True)
class ResearchSignal:
    analyst: str
    symbol: str
    direction: str
    confidence: float
    rationale: str
    observed_at: datetime


@dataclass(frozen=True)
class ResearchDecision:
    symbol: str
    direction: str
    confidence: float
    analyst_count: int
    evidence_sha256: str
    status: str = "research_only"


def evaluate_signals(signals: list[ResearchSignal], *, now: datetime,
                     allowed_analysts: frozenset[str],
                     max_age_seconds: int = 60,
                     minimum_analysts: int = 2,
                     minimum_confidence: float = 0.65) -> ResearchDecision | None:
    """Independent agreement is required; never authorizes an order.

    One vote per approved analyst. Conflicting directions or stale data abstain.
    Confidence is a descriptive consensus score, not calibrated win probability.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if not 0 < minimum_confidence <= 1 or minimum_analysts < 2:
        raise ValueError("invalid consensus requirements")
    if not isinstance(max_age_seconds, int) or max_age_seconds <= 0:
        raise ValueError("invalid freshness window")
    if len(signals) < minimum_analysts:
        return None
    names = [s.analyst for s in signals]
    if len(names) != len(set(names)) or any(name not in allowed_analysts for name in names):
        return None
    symbols = {s.symbol for s in signals}
    directions = {s.direction for s in signals}
    if len(symbols) != 1 or len(directions) != 1:
        return None
    symbol, direction = next(iter(symbols)), next(iter(directions))
    if symbol not in {"BTC/USD", "ETH/USD"} or direction not in {"buy", "hold", "sell"}:
        return None
    for signal in signals:
        timestamp = signal.observed_at
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            return None
        age = (now.astimezone(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds()
        if not 0 <= age <= max_age_seconds or not isfinite(signal.confidence) or not 0 <= signal.confidence <= 1:
            return None
    confidence = min(s.confidence for s in signals)
    if confidence < minimum_confidence:
        return None
    evidence = [{"analyst": s.analyst, "symbol": s.symbol, "direction": s.direction,
                 "confidence": s.confidence, "rationale": s.rationale,
                 "observed_at": s.observed_at.astimezone(timezone.utc).isoformat()}
                for s in sorted(signals, key=lambda s: s.analyst)]
    digest = sha256(json.dumps(evidence, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return ResearchDecision(symbol, direction, confidence, len(signals), digest)
