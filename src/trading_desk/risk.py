"""Deterministic paper-trading risk checks; no broker connectivity."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class RiskLimits:
    max_trade_risk_fraction: float = 0.01
    max_daily_loss_fraction: float = 0.03


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str


def check_proposed_risk(equity: float, proposed_risk_usd: float, realized_daily_pnl: float, limits: RiskLimits = RiskLimits()) -> RiskDecision:
    """Reject orders that violate paper risk limits; assumes trusted P&L inputs.

    This is a bootstrap check, not a production risk gateway. It does not
    account for open-position exposure, slippage, fills, or pending orders.
    """
    if not all(isfinite(v) for v in (equity, proposed_risk_usd, realized_daily_pnl,
                                     limits.max_trade_risk_fraction, limits.max_daily_loss_fraction)):
        return RiskDecision(False, "Non-finite risk inputs")
    if equity <= 0 or proposed_risk_usd <= 0:
        return RiskDecision(False, "Equity and proposed risk must be positive")
    if not (0 < limits.max_trade_risk_fraction < 1 and 0 < limits.max_daily_loss_fraction < 1):
        return RiskDecision(False, "Invalid risk limits")
    if realized_daily_pnl <= -equity * limits.max_daily_loss_fraction:
        return RiskDecision(False, "Daily loss limit reached")
    if proposed_risk_usd > equity * limits.max_trade_risk_fraction:
        return RiskDecision(False, "Trade risk exceeds maximum")
    return RiskDecision(True, "Within preliminary risk limits")
