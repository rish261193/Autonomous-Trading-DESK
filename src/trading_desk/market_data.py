"""Read-only Kraken hourly OHLC ingestion. No credentials or order endpoints."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from .research import Bar, validate_bars

SOURCE = "https://api.kraken.com/0/public/OHLC"
PAIRS = {"BTC/USD": "XBTUSD", "ETH/USD": "ETHUSD"}


def parse_kraken_ohlc(payload: dict, *, symbol: str, interval_minutes: int = 60) -> tuple[list[Bar], dict]:
    """Validate Kraken response and discard the final uncommitted candle."""
    if symbol not in PAIRS or interval_minutes != 60:
        raise ValueError("only BTC/USD and ETH/USD hourly candles are supported")
    if not isinstance(payload, dict) or payload.get("error") != []:
        raise ValueError("Kraken API reported an error")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("missing result")
    keys = [key for key in result if key != "last"]
    if len(keys) != 1 or not isinstance(result.get(keys[0]), list):
        raise ValueError("unexpected market data payload")
    raw = result[keys[0]]
    if len(raw) < 4 or len(raw) > 720:
        raise ValueError("insufficient or oversized candle series")
    bars = []
    for candle in raw:
        if not isinstance(candle, list) or len(candle) < 8:
            raise ValueError("invalid OHLC candle")
        stamp = candle[0]
        if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not isfinite(stamp):
            raise ValueError("invalid candle timestamp")
        timestamp = datetime.fromtimestamp(stamp, tz=timezone.utc)
        if int(stamp) % 3600:
            raise ValueError("unaligned hourly candle")
        prices = [float(value) for value in candle[1:5]]
        if not all(isfinite(p) and p > 0 for p in prices):
            raise ValueError("invalid OHLC price")
        opn, high, low, close = prices
        if low > min(opn, close) or high < max(opn, close) or low > high:
            raise ValueError("inconsistent OHLC")
        volume = float(candle[6])
        if not isfinite(volume) or volume < 0:
            raise ValueError("invalid volume")
        bars.append(Bar(timestamp, close))
    # Kraken explicitly documents that its last candle is in progress.
    completed = bars[:-1]
    validate_bars(completed)
    gaps = [int((b.timestamp - a.timestamp).total_seconds() // 3600) - 1
            for a, b in zip(completed, completed[1:])]
    return completed, {
        "source": SOURCE,
        "pair_requested": PAIRS[symbol],
        "pair_returned": keys[0],
        "symbol": symbol,
        "interval_minutes": interval_minutes,
        "completed_candles": len(completed),
        "excluded_incomplete_candles": 1,
        "missing_hourly_intervals": sum(max(0, gap) for gap in gaps),
        "first_timestamp": completed[0].timestamp.isoformat(),
        "last_timestamp": completed[-1].timestamp.isoformat(),
        "warning": "API is capped at 720 recent candles; missing intervals are reported, never interpolated.",
    }


def fetch_kraken_hourly(symbol: str, *, timeout: float = 15) -> tuple[list[Bar], dict]:
    if symbol not in PAIRS:
        raise ValueError("unsupported symbol")
    url = SOURCE + "?" + urlencode({"pair": PAIRS[symbol], "interval": 60})
    with urlopen(url, timeout=timeout) as response:
        payload = json.load(response)
    return parse_kraken_ohlc(payload, symbol=symbol)


def save_dataset(bars: list[Bar], metadata: dict, *, output_prefix: str) -> dict:
    validate_bars(bars)
    csv_path = Path(output_prefix + ".csv")
    json_path = Path(output_prefix + ".metadata.json")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["timestamp", "close"])
        for bar in bars:
            writer.writerow([bar.timestamp.isoformat(), format(bar.close, ".17g")])
    digest = sha256(csv_path.read_bytes()).hexdigest()
    manifest = {**metadata, "data_sha256": digest,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "data_file": csv_path.name}
    json_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch read-only hourly Kraken candles")
    parser.add_argument("--symbol", required=True, choices=tuple(PAIRS))
    parser.add_argument("--output-prefix", required=True)
    args = parser.parse_args()
    bars, metadata = fetch_kraken_hourly(args.symbol)
    print(json.dumps(save_dataset(bars, metadata, output_prefix=args.output_prefix), indent=2))


if __name__ == "__main__":
    main()
