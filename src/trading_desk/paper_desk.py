"""Deterministic in-memory spot paper ledger, not a broker or live trading system.

Entry checks fail closed on missing marks. Stops define *planned* exposure;
this prototype does not execute stops, model fills, or persist its state.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .gateway import GatewayState, OrderIntent, authorize


def _positive(value: float) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and isfinite(value) and value > 0)


@dataclass(frozen=True)
class PaperPosition:
    symbol: str
    quantity: float
    entry_price: float
    stop_price: float
    risk_usd: float


class PaperDesk:
    """Single-process long-only ledger. Never connect directly to a broker."""

    def __init__(self, initial_equity: float = 500.0):
        if not _positive(initial_equity):
            raise ValueError("Initial equity must be positive and finite")
        self.cash_usd = float(initial_equity)
        self.day_start_equity_usd = float(initial_equity)
        self.daily_realized_pnl_usd = 0.0
        self.positions: list[PaperPosition] = []
        self.marks: dict[str, float] = {}
        self.kill_switch = False

    def mark(self, symbol: str, price: float) -> None:
        """Record a mark; callers must independently establish freshness."""
        if symbol not in {"BTC/USD", "ETH/USD"} or not _positive(price):
            raise ValueError("Invalid mark")
        self.marks[symbol] = float(price)

    def equity(self) -> float:
        if any(p.symbol not in self.marks for p in self.positions):
            raise ValueError("Missing position mark")
        value = self.cash_usd + sum(p.quantity * self.marks[p.symbol]
                                    for p in self.positions)
        if not isfinite(value):
            raise ValueError("Invalid marked equity")
        return value

    def enter(self, *, strategy_id: str, symbol: str, price: float,
              stop_price: float, quantity: float, strategy_authorized: bool,
              market_data_fresh: bool) -> bool:
        """Authorize before mutating cash or positions; never trust supplied P&L."""
        if not all(_positive(v) for v in (price, stop_price, quantity)):
            return False
        if stop_price >= price or symbol not in {"BTC/USD", "ETH/USD"}:
            return False
        # The execution price must be the current independently supplied mark.
        if not market_data_fresh or self.marks.get(symbol) != price:
            return False
        notional = price * quantity
        risk = (price - stop_price) * quantity
        if not isfinite(notional) or not isfinite(risk):
            return False
        try:
            marked_equity = self.equity()
        except ValueError:
            return False
        # Convert per-unit stop distances to dollars; include existing exposure.
        open_risk = sum(max(0.0, max(p.entry_price, self.marks[p.symbol]) -
                            p.stop_price) * p.quantity for p in self.positions)
        state = GatewayState(
            equity_usd=marked_equity,
            day_start_equity_usd=self.day_start_equity_usd,
            # Equity delta captures realized and unrealized P&L exactly once.
            daily_realized_pnl_usd=marked_equity - self.day_start_equity_usd,
            open_risk_usd=open_risk,
            kill_switch=self.kill_switch,
            strategy_authorized=strategy_authorized,
            market_data_fresh=market_data_fresh,
            daily_unrealized_pnl_usd=0.0,
        )
        intent = OrderIntent(strategy_id, symbol, "buy", notional, risk)
        if not authorize(intent, state).allowed or notional > self.cash_usd:
            return False
        self.cash_usd -= notional
        self.positions.append(PaperPosition(symbol, quantity, price, stop_price, risk))
        return True

    def close(self, index: int, price: float) -> float:
        """Close a whole paper position at an explicit synthetic fill price."""
        if (not isinstance(index, int) or isinstance(index, bool) or
                index < 0 or index >= len(self.positions) or not _positive(price)):
            raise ValueError("Invalid close")
        position = self.positions[index]
        if self.marks.get(position.symbol) != price:
            raise ValueError("Close price must equal current mark")
        proceeds = position.quantity * price
        pnl = position.quantity * (price - position.entry_price)
        if not isfinite(proceeds) or not isfinite(pnl):
            raise ValueError("Invalid close valuation")
        self.cash_usd += proceeds
        self.daily_realized_pnl_usd += pnl
        self.positions.pop(index)
        return pnl

    def reset_daily_baseline(self) -> None:
        """Accounting reset only; existing positions remain open."""
        self.day_start_equity_usd = self.equity()
        self.daily_realized_pnl_usd = 0.0

    def halt(self) -> None:
        self.kill_switch = True
