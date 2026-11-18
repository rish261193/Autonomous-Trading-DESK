"""Independent, fail-closed *preliminary* risk authorization.

This module does not place orders. Production authorization must additionally
verify positions, pending orders, timestamps, order minimums, and fill state.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class GatewayLimits:
    max_risk_fraction: float = 0.01
    max_daily_loss_fraction: float = 0.03


@dataclass(frozen=True)
class OrderIntent:
    strategy_id: str
    symbol: str
    side: str
    notional_usd: float
    worst_case_loss_usd: float


@dataclass(frozen=True)
class GatewayState:
    equity_usd: float
    day_start_equity_usd: float
    daily_realized_pnl_usd: float
    open_risk_usd: float
    kill_switch: bool
    strategy_authorized: bool
    market_data_fresh: bool
    daily_unrealized_pnl_usd: float = 0.0


@dataclass(frozen=True)
class GatewayDecision:
    allowed: bool
    reason: str


def authorize(intent: OrderIntent, state: GatewayState,
              limits: GatewayLimits = GatewayLimits()) -> GatewayDecision:
    """Reject unknown, unsafe, stale, or unauthorized requests by default."""
    if state.kill_switch:
        return GatewayDecision(False, "Kill switch active")
    if not state.strategy_authorized:
        return GatewayDecision(False, "Strategy not authorized")
    if not state.market_data_fresh:
        return GatewayDecision(False, "Market data stale")
    values = (intent.notional_usd, intent.worst_case_loss_usd, state.equity_usd,
              state.day_start_equity_usd, state.daily_realized_pnl_usd, state.open_risk_usd,\n              state.daily_unrealized_pnl_usd,
              limits.max_risk_fraction, limits.max_daily_loss_fraction)
    if not all(isfinite(x) for x in values):
        return GatewayDecision(False, "Non-finite input")
    if (state.equity_usd <= 0 or state.day_start_equity_usd <= 0 or
        intent.notional_usd <= 0 or intent.worst_case_loss_usd <= 0 or
        state.open_risk_usd < 0 or not 0 < limits.max_risk_fraction < 1 or
        not 0 < limits.max_daily_loss_fraction < 1):
        return GatewayDecision(False, "Invalid risk inputs")
    if not intent.strategy_id or intent.symbol not in {"BTC/USD", "ETH/USD"}:
        return GatewayDecision(False, "Unknown strategy or symbol")
    if intent.side != "buy":
        return GatewayDecision(False, "Spot-only buy intents supported")
    if intent.notional_usd > state.equity_usd:
        return GatewayDecision(False, "Notional exceeds equity")
    if state.daily_realized_pnl_usd <= -state.day_start_equity_usd * limits.max_daily_loss_fraction:
        return GatewayDecision(False, "Daily loss threshold breached")
    if intent.worst_case_loss_usd + state.open_risk_usd > state.equity_usd * limits.max_risk_fraction:
        return GatewayDecision(False, "Total open risk exceeds one percent")
    return GatewayDecision(True, "Passed preliminary gateway checks")
