"""In-memory guarded paper-entry prototype; no broker, persistence, or live execution.

All entry orders are sized from an explicit stop and independently checked by
the deterministic gateway. This is NOT a production portfolio or order manager.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .gateway import GatewayState, OrderIntent, authorize


@dataclass(frozen=True)
class PaperPosition:
    symbol: str
    quantity: float
    entry_price: float
    stop_price: float
    risk_usd: float


class PaperDesk:
    """Single-process, buy-only paper ledger with fail-closed entry checks."""

    def __init__(self, initial_equity: float = 500.0):
        if not isfinite(initial_equity) or initial_equity <= 0:
            raise ValueError("Initial equity must be positive and finite")
        self.cash_usd = float(initial_equity)
        self.day_start_equity_usd = float(initial_equity)
        self.daily_realized_pnl_usd = 0.0
        self.positions: list[PaperPosition] = []
        self.kill_switch = False

    def enter(self, *, strategy_id: str, symbol: str, price: float,
              stop_price: float, quantity: float, strategy_authorized: bool,
              market_data_fresh: bool, daily_unrealized_pnl_usd: float = 0.0) -> bool:
        """Return False without changing holdings when any check fails.

        Risk is derived from quantity and stop distance, never supplied by
        the strategy. Stop execution/slippage is NOT simulated here.
        """
        numbers = (price, stop_price, quantity, daily_unrealized_pnl_usd)
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                   and isfinite(v) for v in numbers):
            return False
        if price <= 0 or stop_price <= 0 or stop_price >= price or quantity <= 0:
            return False
        notional = price * quantity
        risk = (price - stop_price) * quantity
        if not isfinite(notional) or not isfinite(risk):
            return False
        state = GatewayState(
            equity_usd=self.cash_usd + sum(p.quantity * p.entry_price for p in self.positions),
            day_start_equity_usd=self.day_start_equity_usd,
            daily_realized_pnl_usd=self.daily_realized_pnl_usd,
            open_risk_usd=sum(p.risk_usd for p in self.positions),
            kill_switch=self.kill_switch,
            strategy_authorized=strategy_authorized,
            market_data_fresh=market_data_fresh,
            daily_unrealized_pnl_usd=daily_unrealized_pnl_usd,
        )
        intent = OrderIntent(strategy_id, symbol, "buy", notional, risk)
        if not authorize(intent, state).allowed or notional > self.cash_usd:
            return False
        self.cash_usd -= notional
        self.positions.append(PaperPosition(symbol, quantity, price, stop_price, risk))
        return True

    def halt(self) -> None:
        """Block all subsequent new entries; existing holdings remain."""
        self.kill_switch = True
