"""Read-only CCXT adapter for completed Kraken hourly OHLCV candles.

This module deliberately never creates exchange credentials or calls trading endpoints.
Kraken's recent OHLC endpoint is not a source for a 12-month holdout.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import csv
import json
from math import isfinite
from pathlib import Path
from typing import Any

SUPPORTED = frozenset({"BTC/USD", "ETH/USD"})
TIMEFRAME = "1h"


def normalize_completed_ohlcv(
    rows: list[list[Any]], *, symbol: str, now_ms: int
) -> tuple[list[tuple[int, float, float, float, float, float]], dict]:
    """Fail closed on invalid/duplicate/gapped or incomplete exchange candles."""
    if symbol not in SUPPORTED:
        raise ValueError("unsupported symbol")
    if isinstance(now_ms, bool) or not isinstance(now_ms, int) or now_ms <= 0:
        raise ValueError("invalid reference clock")
    if not rows:
        raise ValueError("no OHLCV candles")
    normalized = []
    previous = None
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != 6:
            raise ValueError("expected [timestamp,open,high,low,close,volume]")
        stamp = row[0]
        if isinstance(stamp, bool) or not isinstance(stamp, int) or stamp < 0 or stamp % 3_600_000:
            raise ValueError("invalid hourly timestamp")
        if previous is not None and stamp <= previous:
            raise ValueError("duplicate or out-of-order candle")
        previous = stamp
        try:
            values = tuple(float(v) for v in row[1:])
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("invalid candle value") from exc
        if not all(isfinite(v) for v in values):
            raise ValueError("non-finite candle")
        opn, high, low, close, volume = values
        if min(opn, high, low, close) <= 0 or volume < 0:
            raise ValueError("invalid price or volume")
        if high < max(opn, close) or low > min(opn, close) or low > high:
            raise ValueError("inconsistent OHLC")
        if stamp + 3_600_000 <= now_ms:
            normalized.append((stamp, *values))
    if not normalized:
        raise ValueError("no completed candles")
    gaps = sum((b[0] - a[0]) // 3_600_000 - 1 for a, b in zip(normalized, normalized[1:]))
    if gaps:
        raise ValueError(f"missing {gaps} hourly candles; refuse incomplete dataset")
    return normalized, {
        "exchange": "kraken", "symbol": symbol, "timeframe": TIMEFRAME,
        "completed_candles": len(normalized), "excluded_unfinished": len(rows) - len(normalized),
        "first_timestamp": datetime.fromtimestamp(normalized[0][0] / 1000, timezone.utc).isoformat(),
        "last_timestamp": datetime.fromtimestamp(normalized[-1][0] / 1000, timezone.utc).isoformat(),
        "warning": "Recent Kraken OHLCV is insufficient for a 12-month untouched holdout.",
    }


def fetch_public_hourly(symbol: str, *, exchange: Any = None, now_ms: int | None = None):
    """Dependency-injected read-only fetch; caller owns exchange lifecycle."""
    if symbol not in SUPPORTED:
        raise ValueError("unsupported symbol")
    if exchange is None:
        try:
            import ccxt
        except ImportError as exc:
            raise RuntimeError("install optional dependency: pip install ccxt") from exc
        exchange = ccxt.kraken({"enableRateLimit": True})
    if getattr(exchange, "id", None) != "kraken":
        raise ValueError("only Kraken is approved")
    if not isinstance(getattr(exchange, "has", None), dict) or not exchange.has.get("fetchOHLCV"):
        raise ValueError("exchange does not support OHLCV")
    if now_ms is None:
        from time import time
        now_ms = int(time() * 1000)
    rows = exchange.fetch_ohlcv(symbol, TIMEFRAME)
    return normalize_completed_ohlcv(rows, symbol=symbol, now_ms=now_ms)


def save_ohlcv(rows, metadata: dict, *, output_prefix: str) -> dict:
    """Persist full OHLCV and SHA-256 provenance; never silently overwrite."""
    path = Path(output_prefix + ".csv")
    manifest_path = Path(output_prefix + ".metadata.json")
    if path.exists() or manifest_path.exists():
        raise FileExistsError("dataset already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for stamp, opn, high, low, close, volume in rows:
            writer.writerow([datetime.fromtimestamp(stamp / 1000, timezone.utc).isoformat(),
                             *[format(x, ".17g") for x in (opn, high, low, close, volume)]])
    manifest = {**metadata, "data_sha256": sha256(path.read_bytes()).hexdigest(), "data_file": path.name}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
