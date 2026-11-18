"""Atomic idempotent pending order reservations for a SQLite paper desk.

Reservations are not exchange orders. No real fills or partial fills are supported.
"""
import json
import math
import sqlite3

from .gateway import GatewayState, OrderIntent, authorize


class PendingOrders:
    def __init__(self, persistent_desk):
        self.desk = persistent_desk
        with self.desk._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS reservations "
                       "(order_id TEXT PRIMARY KEY, payload TEXT NOT NULL, "
                       "status TEXT NOT NULL CHECK(status IN ('pending','cancelled','filled')))")

    @staticmethod
    def _pending(db):
        return [json.loads(r[0]) for r in db.execute(
            "SELECT payload FROM reservations WHERE status='pending'")]

    def reserve(self, order_id, *, strategy_id, symbol, price, stop_price,
                quantity, strategy_authorized, market_data_fresh):
        if not isinstance(order_id, str) or not 0 < len(order_id) <= 128:
            return False
        values = (price, stop_price, quantity)
        if not all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in values):
            return False
        if stop_price >= price:
            return False
        with self.desk._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM reservations WHERE order_id=?",
                          (order_id,)).fetchone():
                db.commit()
                return False
            desk = self.desk._load(db)
            pending = self._pending(db)
            if desk.marks.get(symbol) != price:
                db.commit()
                return False
            try:
                equity = desk.equity()
            except ValueError:
                db.commit()
                return False
            notional = price * quantity
            risk = (price - stop_price) * quantity
            cash_reserved = sum(p["notional"] for p in pending)
            risk_reserved = sum(p["risk"] for p in pending)
            open_risk = sum(max(0, max(p.entry_price, desk.marks[p.symbol]) -
                                p.stop_price) * p.quantity for p in desk.positions)
            state = GatewayState(equity, desk.day_start_equity_usd,
                                 equity - desk.day_start_equity_usd,
                                 open_risk + risk_reserved, desk.kill_switch,
                                 strategy_authorized, market_data_fresh)
            intent = OrderIntent(strategy_id, symbol, "buy", notional, risk)
            if (not math.isfinite(notional) or not math.isfinite(risk) or
                    notional + cash_reserved > desk.cash_usd or
                    not authorize(intent, state).allowed):
                db.commit()
                return False
            payload = dict(strategy_id=strategy_id, symbol=symbol, price=price,
                           stop_price=stop_price, quantity=quantity,
                           strategy_authorized=strategy_authorized,
                           market_data_fresh=market_data_fresh,
                           notional=notional, risk=risk)
            db.execute("INSERT INTO reservations VALUES (?,?,'pending')",
                       (order_id, json.dumps(payload, sort_keys=True, allow_nan=False)))
            self.desk._event(db, "reserve", {"order_id": order_id})
            db.commit()
            return True

    def cancel(self, order_id):
        with self.desk._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE reservations SET status='cancelled' "
                "WHERE order_id=? AND status='pending'", (order_id,)).rowcount
            if changed:
                self.desk._event(db, "cancel", {"order_id": order_id})
            db.commit()
            return bool(changed)

    def fill(self, order_id, *, strategy_authorized=False, market_data_fresh=False):
        """Synthetic fill; require renewed authorization and freshness."""
        if strategy_authorized is not True or market_data_fresh is not True:
            return False
        with self.desk._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload FROM reservations WHERE order_id=? AND status='pending'",
                (order_id,)).fetchone()
            if row is None:
                db.commit()
                return False
            payload = json.loads(row[0])
            desk = self.desk._load(db)
            others = sum((p["risk"] for p in self._pending(db)
                          if p is not None), 0.0) - payload["risk"]
            reserved_cash = sum(p["notional"] for p in self._pending(db))
            if (desk.marks.get(payload["symbol"]) != payload["price"] or
                    reserved_cash > desk.cash_usd):
                db.commit()
                return False
            equity = desk.equity()
            open_risk = sum(max(0, max(p.entry_price, desk.marks[p.symbol]) -
                                p.stop_price) * p.quantity for p in desk.positions)
            state = GatewayState(equity, desk.day_start_equity_usd,
                                 equity - desk.day_start_equity_usd,
                                 open_risk + max(0, others), desk.kill_switch,
                                 strategy_authorized,
                                 market_data_fresh)
            intent = OrderIntent(payload["strategy_id"], payload["symbol"], "buy",
                                 payload["notional"], payload["risk"])
            if not authorize(intent, state).allowed:
                db.commit()
                return False
            keys = ("strategy_id", "symbol", "price", "stop_price", "quantity",
                    "strategy_authorized", "market_data_fresh")
            entry = {k: payload[k] for k in keys}
            entry["strategy_authorized"] = strategy_authorized
            entry["market_data_fresh"] = market_data_fresh
            if not desk.enter(**entry):
                db.commit()
                return False
            self.desk._save(db, desk)
            db.execute("UPDATE reservations SET status='filled' WHERE order_id=?",
                       (order_id,))
            self.desk._event(db, "fill", {"order_id": order_id})
            db.commit()
            return True
