"""Offline signal evaluation against future closes; no order authorization.

Signals are assessed only after the forward horizon has elapsed. The baseline is
buy-and-hold over the same observation windows. Overlapping windows are NOT
independent statistical samples.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from math import isfinite
import json

from .intelligence import ResearchDecision
from .research import Bar, Costs, validate_bars


@dataclass(frozen=True)
class SignalOutcome:
    observed_at: datetime
    horizon_end: datetime
    direction: str
    gross_return_pct: float
    net_return_pct: float
    baseline_return_pct: float
    correct_direction: bool


def evaluate_history(bars: list[Bar], decisions: dict[datetime, ResearchDecision],
                     *, horizon_bars: int = 1, costs: Costs = Costs()) -> dict:
    """Score decisions at exact bar timestamps with next-bar/horizon close exits.

    A buy means long; sell is an abstention from spot exposure, not a short.
    Hold is also abstention. This is NOT a tradable fill model. A round-trip
    cost assumption applies to buys only. Missing future bars are excluded.
    """
    validate_bars(bars)
    if not isinstance(horizon_bars, int) or isinstance(horizon_bars, bool) or horizon_bars < 1:
        raise ValueError("horizon_bars must be a positive integer")
    if not all(isfinite(v) and 0 <= v < 10000 for v in (costs.fee_bps, costs.slippage_bps)):
        raise ValueError("invalid costs")
    cost_fraction = (costs.fee_bps + costs.slippage_bps) / 10000
    if cost_fraction >= 1:
        raise ValueError("invalid combined costs")
    index = {bar.timestamp: i for i, bar in enumerate(bars)}
    if len(index) != len(bars):
        raise ValueError("duplicate bars")
    outcomes = []
    for timestamp, decision in sorted(decisions.items()):
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("decision timestamps must be timezone-aware")
        timestamp = timestamp.astimezone(timezone.utc)
        if timestamp not in index:
            raise ValueError("decision timestamp not in historical bars")
        if decision.status != "research_only" or decision.symbol not in {"BTC/USD", "ETH/USD"}:
            raise ValueError("invalid research decision")
        if decision.direction not in {"buy", "sell", "hold"}:
            raise ValueError("invalid direction")
        if not isfinite(decision.confidence) or not 0 <= decision.confidence <= 1:
            raise ValueError("invalid confidence")
        i = index[timestamp]
        if i + horizon_bars >= len(bars):
            continue
        start, end = bars[i].close, bars[i + horizon_bars].close
        gross = end / start - 1
        # For long-only research, exit proceeds are reduced by costs, while
        # acquisition costs increase the initial cost basis.
        net = ((end * (1 - cost_fraction)) / (start * (1 + cost_fraction)) - 1) if decision.direction == "buy" else 0.0
        outcomes.append(SignalOutcome(timestamp, bars[i + horizon_bars].timestamp,
                                      decision.direction, 100 * (gross if decision.direction == "buy" else 0),
                                      100 * net, 100 * gross,
                                      (gross > 0 if decision.direction == "buy" else gross <= 0)))
    traded = [o for o in outcomes if o.direction == "buy"]
    raw = [{"timestamp": o.observed_at.isoformat(), "end": o.horizon_end.isoformat(),
            "direction": o.direction, "net": o.net_return_pct,
            "baseline": o.baseline_return_pct} for o in outcomes]
    digest = sha256(json.dumps(raw, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return {
        "status": "unverified_research",
        "evaluated": len(outcomes),
        "long_signals": len(traded),
        "abstentions": len(outcomes) - len(traded),
        "long_win_rate": (sum(o.net_return_pct > 0 for o in traded) / len(traded) if traded else None),
        "mean_long_net_return_pct": (sum(o.net_return_pct for o in traded) / len(traded) if traded else None),
        "mean_baseline_return_pct": (sum(o.baseline_return_pct for o in outcomes) / len(outcomes) if outcomes else None),
        "mean_signal_net_return_pct": (sum(o.net_return_pct for o in outcomes) / len(outcomes) if outcomes else None),
        "evidence_sha256": digest,
        "caveats": [
            "Close-to-close hypothetical execution; no actual fills, stops, risk gateway or liquidity.",
            "Signals must have been generated without access to future bars; this function cannot verify provenance.",
            "Overlapping forward windows are dependent; means are not compounded portfolio returns.",
            "Sell and hold mean no spot position, never short exposure.",
            "No statistical significance or trading edge established by this report alone.",
        ],
    }
