"""Offline experiment runner for timestamped, externally supplied research signals.

CSV prices: timestamp,close (UTC or offset ISO-8601).
CSV signals: timestamp,symbol,direction,confidence,analyst_count,evidence_sha256.
Signals must be generated and timestamped before outcomes become observable.
No data download, LLM calls, exchange access, or trade execution.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from hashlib import sha256
from math import isfinite
from pathlib import Path

from .intelligence import ResearchDecision
from .research import Costs, load_csv
from .signal_evaluation import evaluate_history


def load_decisions(path: str, *, expected_symbol: str) -> dict[datetime, ResearchDecision]:
    if expected_symbol not in {"BTC/USD", "ETH/USD"}:
        raise ValueError("unsupported symbol")
    decisions: dict[datetime, ResearchDecision] = {}
    with open(path, newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"timestamp", "symbol", "direction", "confidence",
                    "analyst_count", "evidence_sha256"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("missing signal CSV columns")
        for row in reader:
            timestamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("signal timestamp must be timezone-aware")
            timestamp = timestamp.astimezone(timezone.utc)
            confidence = float(row["confidence"])
            count = int(row["analyst_count"])
            symbol = row["symbol"]
            direction = row["direction"]
            evidence = row["evidence_sha256"]
            if (symbol != expected_symbol or direction not in {"buy", "hold", "sell"}
                    or not isfinite(confidence) or not 0 <= confidence <= 1
                    or count < 2 or len(evidence) != 64
                    or any(c not in "0123456789abcdef" for c in evidence)):
                raise ValueError("invalid research signal")
            if timestamp in decisions:
                raise ValueError("duplicate signal timestamp")
            decisions[timestamp] = ResearchDecision(symbol, direction, confidence, count, evidence)
    return decisions


def _file_sha256(path: str) -> str:
    digest = sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_experiment(*, prices_csv: str, signals_csv: str, symbol: str,
                   horizon_bars: int = 1, fee_bps: float = 10,
                   slippage_bps: float = 5) -> dict:
    bars = load_csv(prices_csv)
    decisions = load_decisions(signals_csv, expected_symbol=symbol)
    report = evaluate_history(bars, decisions, horizon_bars=horizon_bars,
                              costs=Costs(fee_bps, slippage_bps))
    report["price_data_sha256"] = _file_sha256(prices_csv)
    report["signal_data_sha256"] = _file_sha256(signals_csv)
    report["evaluation_settings"] = {"horizon_bars": horizon_bars,
                                     "fee_bps": fee_bps,
                                     "slippage_bps": slippage_bps}
    report["symbol"] = symbol
    report["price_bars"] = len(bars)
    report["supplied_signals"] = len(decisions)
    report["provenance_warning"] = (
        "CSV timestamps and evidence hashes are self-reported. "
        "This runner cannot establish that signals predated future prices. "
        "Use append-only external capture for credible out-of-sample evidence."
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline research-only signal benchmark")
    parser.add_argument("--prices", required=True)
    parser.add_argument("--signals", required=True)
    parser.add_argument("--symbol", required=True, choices=("BTC/USD", "ETH/USD"))
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--fee-bps", type=float, default=10)
    parser.add_argument("--slippage-bps", type=float, default=5)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = run_experiment(prices_csv=args.prices, signals_csv=args.signals,
                            symbol=args.symbol, horizon_bars=args.horizon,
                            fee_bps=args.fee_bps, slippage_bps=args.slippage_bps)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
                      encoding="utf-8")


if __name__ == "__main__":
    main()
