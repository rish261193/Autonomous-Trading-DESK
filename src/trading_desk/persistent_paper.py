"""SQLite-backed transactional paper ledger. No broker integration.

Every operation reloads the committed snapshot under BEGIN IMMEDIATE and saves
the resulting state in one transaction. Use one SQLite database per paper desk.

Integrity (audit F-07): every event is timestamped and SHA-256 hash-chained,
and startup reconciliation replays the event log and requires it to reproduce
the stored snapshot. This detects edits to the snapshot alone, or to the log
alone. It does NOT stop an attacker who rewrites both and recomputes the
chain; anchor ``ledger_head()`` outside this database for that.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from .paper_desk import PaperDesk, PaperPosition


def _system_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PersistentPaperDesk:
    #: Largest tolerated difference between a caller-supplied time and the
    #: trusted clock. Restores the guard from 6607789 (reverted in d6072a6).
    MAX_CLOCK_SKEW_SECONDS = 120

    def __init__(self, path: str, initial_equity: float = 500.0, *, clock=None):
        """``clock`` is the trusted UTC time source, injected only by the
        process that owns the ledger (tests use a deterministic clock)."""
        self._clock = _system_utc_now if clock is None else clock
        self.path = str(path)
        if self.path == ":memory:":
            raise ValueError("Use a file-backed SQLite database")
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, payload TEXT NOT NULL, created_at_utc TEXT, prev_hash TEXT, hash TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS daily_clock (id INTEGER PRIMARY KEY CHECK(id=1), utc_date TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO daily_clock(id,utc_date) VALUES (1,?)", (self.now().date().isoformat(),))
            db.execute("BEGIN IMMEDIATE")
            self._migrate_event_chain(db)
            if db.execute("SELECT 1 FROM state WHERE id=1").fetchone() is None:
                desk = PaperDesk(initial_equity)
                self._save(db, desk)
                self._event(db, "initialize", {"initial_equity": initial_equity})
            db.commit()
        # Fail closed on corrupt persisted state, rather than silently reinitializing.
        self.reconcile()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("PRAGMA synchronous=FULL")
            yield db
        finally:
            db.close()

    @staticmethod
    def _chain_hash(prev_hash, kind, payload_text, created_at):
        material = "\x1f".join((prev_hash, kind, payload_text, created_at))
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _event(self, db, kind, payload):
        """Append a timestamped, hash-chained event inside the caller's transaction."""
        text = json.dumps(payload, sort_keys=True, allow_nan=False)
        created_at = self.now().isoformat()
        row = db.execute("SELECT hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash = "" if row is None else row[0]
        if prev_hash is None:
            raise ValueError("Unchained event log; refusing to append")
        db.execute("INSERT INTO events(kind,payload,created_at_utc,prev_hash,hash) "
                   "VALUES (?,?,?,?,?)",
                   (kind, text, created_at, prev_hash,
                    self._chain_hash(prev_hash, kind, text, created_at)))

    def _migrate_event_chain(self, db):
        """Add integrity columns to pre-audit databases and chain legacy rows."""
        columns = {r[1] for r in db.execute("PRAGMA table_info(events)")}
        missing = [c for c in ("created_at_utc", "prev_hash", "hash") if c not in columns]
        for column in missing:
            db.execute(f"ALTER TABLE events ADD COLUMN {column} TEXT")
        if missing:
            prev = ""
            for seq, kind, text in db.execute(
                    "SELECT seq, kind, payload FROM events ORDER BY seq").fetchall():
                digest = self._chain_hash(prev, kind, text, "")
                db.execute("UPDATE events SET created_at_utc='', prev_hash=?, hash=? "
                           "WHERE seq=?", (prev, digest, seq))
                prev = digest

    def ledger_head(self) -> tuple[int, str]:
        """(sequence, hash) of the newest event, for anchoring outside the DB."""
        with self._connect() as db:
            row = db.execute("SELECT seq, hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        if row is None or not row[1]:
            raise ValueError("Empty or unchained event log")
        return row[0], row[1]

    @staticmethod
    def _load(db):
        row = db.execute("SELECT payload FROM state WHERE id=1").fetchone()
        if row is None:
            raise ValueError("Missing persistent state")
        data = json.loads(row[0])
        desk = PaperDesk(data["day_start_equity_usd"])
        desk.cash_usd = data["cash_usd"]
        desk.day_start_equity_usd = data["day_start_equity_usd"]
        desk.daily_realized_pnl_usd = data["daily_realized_pnl_usd"]
        desk.kill_switch = data["kill_switch"]
        desk.marks = data["marks"]
        desk.positions = [PaperPosition(**p) for p in data["positions"]]
        # Detect corrupt or non-finite financial values before trading.
        from math import isfinite
        values = [desk.cash_usd, desk.day_start_equity_usd,
                  desk.daily_realized_pnl_usd, *desk.marks.values()]
        for p in desk.positions:
            values.extend([p.quantity, p.entry_price, p.stop_price, p.risk_usd])
        if (not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                    and isfinite(v) for v in values)
                or desk.cash_usd < 0 or not isinstance(desk.kill_switch, bool)):
            raise ValueError("Corrupt persistent financial state")
        return desk

    @staticmethod
    def _save(db, desk):
        data = {
            "cash_usd": desk.cash_usd,
            "day_start_equity_usd": desk.day_start_equity_usd,
            "daily_realized_pnl_usd": desk.daily_realized_pnl_usd,
            "kill_switch": desk.kill_switch,
            "marks": desk.marks,
            "positions": [asdict(p) for p in desk.positions],
        }
        db.execute("INSERT INTO state(id,payload) VALUES(1,?) "
                   "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                   (json.dumps(data, sort_keys=True, allow_nan=False),))

    def snapshot(self):
        with self._connect() as db:
            return self._load(db)

    def reconcile(self):
        """Fail closed on malformed snapshots, invalid reservations, or broken totals."""
        from math import isfinite
        with self._connect() as db:
            desk = self._load(db)
            if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reservations'").fetchone():
                pending_cash = 0.0
                pending_risk = 0.0
                for payload_text, status in db.execute("SELECT payload,status FROM reservations"):
                    payload = json.loads(payload_text)
                    if (status not in ("pending", "filled", "cancelled") or
                        payload.get("symbol") not in {"BTC/USD", "ETH/USD"} or
                        not isinstance(payload.get("strategy_id"), str)):
                        raise ValueError("Corrupt reservation")
                    price, stop, qty = (payload.get(k) for k in ("price", "stop_price", "quantity"))
                    if (not all(type(v) in (int, float) and isfinite(v) and v > 0
                                for v in (price, stop, qty)) or stop >= price or
                        abs(payload.get("notional", -1) - price * qty) > 1e-7 or
                        abs(payload.get("risk", -1) - (price - stop) * qty) > 1e-7):
                        raise ValueError("Corrupt reservation economics")
                    if status == "pending":
                        pending_cash += payload["notional"]
                        pending_risk += payload["risk"]
                if pending_cash > desk.cash_usd + 1e-7:
                    raise ValueError("Pending cash exceeds balance")
            if any(p.symbol not in {"BTC/USD", "ETH/USD"} or
                   not all(isfinite(v) and v > 0 for v in (p.quantity, p.entry_price, p.stop_price, p.risk_usd)) or
                   p.stop_price >= p.entry_price or
                   not isinstance(p.strategy_id, str) or not isinstance(p.order_id, str) or
                   abs(p.risk_usd - (p.entry_price - p.stop_price) * p.quantity) > 1e-7
                   for p in desk.positions):
                raise ValueError("Corrupt persisted positions")
            if any(symbol not in {"BTC/USD", "ETH/USD"} or price <= 0
                   for symbol, price in desk.marks.items()):
                raise ValueError("Corrupt persisted marks")
            if desk.day_start_equity_usd <= 0 or desk.cash_usd < 0:
                raise ValueError("Corrupt persisted equity")
            equity = desk.equity()
            if not isfinite(equity) or equity < 0:
                raise ValueError("Corrupt portfolio valuation")
            result = db.execute("PRAGMA quick_check").fetchone()
            if result is None or result[0] != "ok":
                raise ValueError("SQLite integrity check failed")
            self._verify(db, desk)
            return equity

    def verify_integrity(self) -> dict:
        """Verify the hash chain and that replaying events reproduces state."""
        with self._connect() as db:
            return self._verify(db, self._load(db))

    @staticmethod
    def _same(a, b):
        return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))

    def _verify(self, db, stored):
        rows = db.execute("SELECT seq, kind, payload, created_at_utc, prev_hash, hash "
                          "FROM events ORDER BY seq").fetchall()
        if not rows or rows[0][1] != "initialize":
            raise ValueError("Event log must start with initialize")
        prev = ""
        for seq, kind, text, created_at, prev_hash, digest in rows:
            if (prev_hash != prev or created_at is None or
                    digest != self._chain_hash(prev, kind, text, created_at)):
                raise ValueError(f"Event hash chain broken at seq {seq}")
            prev = digest
        reservations = {}
        if db.execute("SELECT name FROM sqlite_master WHERE type='table' "
                      "AND name='reservations'").fetchone():
            reservations = {oid: (json.loads(text), status) for oid, text, status in
                            db.execute("SELECT order_id, payload, status FROM reservations")}
        replay, seen = None, {}
        for seq, kind, text, *_ in rows:
            event = json.loads(text)
            if kind == "initialize":
                if replay is not None:
                    raise ValueError("Duplicate initialize event")
                replay = PaperDesk(event["initial_equity"])
            elif kind in ("mark", "stop_mark"):
                count, realized, _ = self._mark_and_stop(replay, event["symbol"], event["price"])
                if (count != event.get("triggered", 0) or
                        not self._same(realized, event.get("realized_pnl_usd", 0.0))):
                    raise ValueError(f"Replay mismatch for stop at seq {seq}")
            elif kind == "close":
                index = (replay.index_of(event["order_id"]) if event.get("order_id")
                         else event["index"])
                if not self._same(replay.close(index, event["price"]), event["result"]):
                    raise ValueError(f"Replay mismatch for close at seq {seq}")
            elif kind == "halt":
                replay.halt()
            elif kind == "daily_reset":
                replay.reset_daily_baseline()
            elif kind in ("reserve", "cancel", "fill"):
                order_id = event["order_id"]
                if order_id not in reservations:
                    raise ValueError(f"Event references unknown reservation at seq {seq}")
                seen.setdefault(order_id, []).append(kind)
                if kind == "fill":
                    order = reservations[order_id][0]
                    keys = ("strategy_id", "symbol", "price", "stop_price", "quantity")
                    if any(k in event and event[k] != order[k] for k in keys):
                        raise ValueError(f"Fill event disagrees with reservation at seq {seq}")
                    if not replay.enter(**{k: order[k] for k in keys},
                                        strategy_authorized=True, market_data_fresh=True,
                                        order_id=order_id):
                        raise ValueError(f"Replayed fill rejected at seq {seq}")
            else:
                raise ValueError(f"Unknown event kind at seq {seq}")
        # Databases created before this audit lack position attribution.
        legacy = rows[0][3] == ""
        expected_status = {("reserve",): "pending", ("reserve", "fill"): "filled",
                           ("reserve", "cancel"): "cancelled"}
        for order_id, (_, status) in reservations.items():
            if expected_status.get(tuple(seen.get(order_id, ()))) != status:
                raise ValueError("Reservation status disagrees with event log")
        scalars = ("cash_usd", "day_start_equity_usd", "daily_realized_pnl_usd")
        if (any(not self._same(getattr(replay, k), getattr(stored, k)) for k in scalars) or
                replay.kill_switch != stored.kill_switch or
                replay.marks.keys() != stored.marks.keys() or
                any(not self._same(replay.marks[k], stored.marks[k]) for k in replay.marks) or
                len(replay.positions) != len(stored.positions) or
                any(asdict(a).keys() != asdict(b).keys() or any(
                    (va != vb and not (legacy and vb == "")) if isinstance(va, str)
                    else not self._same(va, vb)
                    for va, vb in zip(asdict(a).values(), asdict(b).values()))
                    for a, b in zip(replay.positions, stored.positions))):
            raise ValueError("Stored snapshot does not match event-log replay")
        return {"events": len(rows), "head_seq": rows[-1][0], "head_hash": prev}

    def _mutate(self, kind, operation, payload):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            desk = self._load(db)
            result = operation(desk)
            self._save(db, desk)
            self._event(db, kind, payload | {"result": result})
            db.commit()
            return result

    @staticmethod
    def _mark_and_stop(desk, symbol, price):
        """Apply a mark and close every position whose stop it crosses."""
        desk.mark(symbol, price)
        count, realized, exits = 0, 0.0, []
        for index in range(len(desk.positions) - 1, -1, -1):
            position = desk.positions[index]
            if position.symbol == symbol and price <= position.stop_price:
                pnl = desk.close(index, price)
                realized += pnl
                count += 1
                exits.append({"order_id": position.order_id,
                              "strategy_id": position.strategy_id,
                              "realized_pnl_usd": pnl})
        return count, realized, exits

    def mark(self, symbol: str, price: float) -> tuple[int, float]:
        """Record a mark and, in the same transaction, stop out any position
        whose stop it crosses (audit F-03: marks used to skip stops)."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            desk = self._load(db)
            count, realized, exits = self._mark_and_stop(desk, symbol, price)
            self._save(db, desk)
            payload = {"symbol": symbol, "price": price, "result": None}
            if count:
                payload |= {"triggered": count, "realized_pnl_usd": realized,
                            "exits": exits}
            self._event(db, "mark", payload)
            db.commit()
            return count, realized

    def enter(self, **kwargs):
        """Disallow direct entries that bypass pending-order reservations."""
        raise RuntimeError("Direct entry disabled: use PendingOrders.reserve/fill")

    @staticmethod
    def _close_at(desk, index, price):
        position = desk.positions[index] if (
            isinstance(index, int) and not isinstance(index, bool)
            and 0 <= index < len(desk.positions)) else None
        pnl = desk.close(index, price)
        return pnl, position

    def close(self, index: int, price: float):
        """Legacy index-based close. Prefer close_position(order_id, price):
        list indices shift when another transaction closes a position."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            desk = self._load(db)
            pnl, position = self._close_at(desk, index, price)
            self._save(db, desk)
            self._event(db, "close", {"index": index, "price": price, "result": pnl,
                                      "order_id": position.order_id,
                                      "strategy_id": position.strategy_id})
            db.commit()
            return pnl

    def close_position(self, order_id: str, price: float) -> float:
        """Close the position opened by ``order_id`` at the current mark."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            desk = self._load(db)
            index = desk.index_of(order_id)
            pnl, position = self._close_at(desk, index, price)
            self._save(db, desk)
            self._event(db, "close", {"index": index, "price": price, "result": pnl,
                                      "order_id": position.order_id,
                                      "strategy_id": position.strategy_id})
            db.commit()
            return pnl

    def apply_stop_mark(self, symbol: str, price: float) -> tuple[int, float]:
        """Mark and close all triggered positions in one SQLite transaction."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            desk = self._load(db)
            count, realized, exits = self._mark_and_stop(desk, symbol, price)
            self._save(db, desk)
            self._event(db, "stop_mark", {
                "symbol": symbol, "price": price,
                "triggered": count, "realized_pnl_usd": realized,
                "exits": exits,
            })
            db.commit()
            return count, realized

    def halt(self):
        return self._mutate("halt", lambda d: d.halt(), {})

    def reset_daily_baseline(self):
        """Legacy manual reset is unsafe: only the clock-driven UTC roll may reset."""
        raise RuntimeError("Manual daily reset disabled; use roll_utc_day")

    def now(self) -> datetime:
        """Current time from the trusted clock, normalized to UTC."""
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ValueError("Trusted clock must return a UTC-aware datetime")
        return value.astimezone(timezone.utc)

    def check_caller_time(self, now) -> datetime:
        """Reject caller-supplied times that disagree with the trusted clock."""
        trusted = self.now()
        if now is None:
            return trusted
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("UTC-aware datetime required")
        if abs((now - trusted).total_seconds()) > self.MAX_CLOCK_SKEW_SECONDS:
            raise ValueError("Caller clock disagrees with trusted clock")
        return now.astimezone(timezone.utc)

    def roll_utc_day(self, *, now=None):
        """Roll at most once per UTC calendar date, transactionally with the ledger."""
        now = self.check_caller_time(now)
        today = now.date().isoformat()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT utc_date FROM daily_clock WHERE id=1").fetchone()
            if row is None:
                raise ValueError("Missing UTC clock")
            if today < row[0]:
                raise ValueError("Clock rollback detected")
            if today == row[0]:
                db.commit()
                return False
            desk = self._load(db)
            desk.reset_daily_baseline()
            self._save(db, desk)
            db.execute("UPDATE daily_clock SET utc_date=? WHERE id=1", (today,))
            self._event(db, "daily_reset", {"utc_date": today})
            db.commit()
            return True
