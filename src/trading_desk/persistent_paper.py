"""SQLite-backed transactional paper ledger. No broker integration.

Every operation reloads the committed snapshot under BEGIN IMMEDIATE and saves
the resulting state in one transaction. Use one SQLite database per paper desk.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from .paper_desk import PaperDesk, PaperPosition


class PersistentPaperDesk:
    def __init__(self, path: str, initial_equity: float = 500.0):
        self.path = str(path)
        if self.path == ":memory:":
            raise ValueError("Use a file-backed SQLite database")
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, payload TEXT NOT NULL)")
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM state WHERE id=1").fetchone() is None:
                desk = PaperDesk(initial_equity)
                self._save(db, desk)
                self._event(db, "initialize", {"initial_equity": initial_equity})
            db.commit()
        # Fail closed on corrupt persisted state, rather than silently reinitializing.
        self.snapshot()

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
    def _event(db, kind, payload):
        db.execute("INSERT INTO events(kind,payload) VALUES (?,?)",
                   (kind, json.dumps(payload, sort_keys=True, allow_nan=False)))

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

    def _mutate(self, kind, operation, payload):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            desk = self._load(db)
            result = operation(desk)
            self._save(db, desk)
            self._event(db, kind, payload | {"result": result})
            db.commit()
            return result

    def mark(self, symbol: str, price: float):
        return self._mutate("mark", lambda d: d.mark(symbol, price),
                            {"symbol": symbol, "price": price})

    def enter(self, **kwargs):
        return self._mutate("enter", lambda d: d.enter(**kwargs), kwargs)

    def close(self, index: int, price: float):
        return self._mutate("close", lambda d: d.close(index, price),
                            {"index": index, "price": price})

    def halt(self):
        return self._mutate("halt", lambda d: d.halt(), {})

    def reset_daily_baseline(self):
        return self._mutate("daily_reset", lambda d: d.reset_daily_baseline(), {})
