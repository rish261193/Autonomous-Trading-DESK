"""Offline research pipeline: train-only selection, holdout, audit, and metrics.

No brokerage connectivity, real-time execution, or profitability claims.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import json

from .audit import append_jsonl, make_experiment_record
from .metrics import evaluate_equity
from .research import Bar, Costs, backtest, grid_search, validate_bars
from .validation import rolling_splits


def research_pipeline(
    bars: list[Bar],
    fast_values: list[int],
    slow_values: list[int],
    train_size: int,
    test_size: int,
    gap: int = 0,
    costs: Costs = Costs(),
    audit_path: str | None = None,
) -> dict:
    """Research-only rolling evaluation with selection performed on training data.

    Each holdout begins after a separate embargo. Slow-window warmup bars are
    taken from prior observations, but no holdout prices inform parameter choice.
    Results use the deliberately simplified research backtester; returns across
    windows must not be interpreted as a continuous deployable portfolio.
    """
    validate_bars(bars)
    splits = rolling_splits(len(bars), train_size, test_size, gap)
    if not fast_values or not slow_values:
        raise ValueError("At least one fast and slow candidate is required")
    data_bytes = "\n".join(f"{b.timestamp.isoformat()},{b.close:.17g}" for b in bars).encode()
    digest = sha256(data_bytes).hexdigest()
    windows = []
    for idx, split in enumerate(splits):
        train = bars[split.train_start:split.train_end]
        candidates = grid_search(train, fast_values, slow_values, costs)
        if not candidates:
            raise ValueError("No valid candidates in training window")
        winner = candidates[0]
        # Include only pre-test observations for the signal warmup.
        warmup_start = split.test_start - winner.slow
        if warmup_start < 0:
            raise ValueError("Insufficient history for test warmup")
        evaluation = bars[warmup_start:split.test_end]
        holdout = backtest(evaluation, winner.fast, winner.slow, costs)
        # These are independent per-window equity outcomes, not a stitched curve.
        summary = evaluate_equity([500.0, holdout.ending_equity])
        windows.append({
            "window": idx + 1,
            "split": asdict(split),
            "selected_on_train": {"fast": winner.fast, "slow": winner.slow},
            "train_net_return_pct": winner.net_return_pct,
            "holdout": asdict(holdout),
            "holdout_two_point_return_pct": summary.net_return_pct,
        })
    report = {
        "status": "unverified_research",
        "data_sha256": digest,
        "windows": windows,
        "costs": asdict(costs),
        "caveats": [
            "Close-price fills are simplified; execution is not realistic.",
            "Overnight liquidation occurs at first next-day observation, not necessarily midnight.",
            "No stops, portfolio-level exposure, independent risk gateway or actual fills.",
            "Window returns are not a continuous portfolio equity curve.",
            "No real-data profitability evidence or statistical significance is established.",
        ],
    }
    if audit_path is not None:
        record = make_experiment_record(
            "sma_rolling_baseline",
            {"fast_values": fast_values, "slow_values": slow_values,
             "train_size": train_size, "test_size": test_size, "gap": gap,
             "costs": asdict(costs)},
            digest,
            {"windows": windows},
            notes="Research only. No trade authorization.",
        )
        append_jsonl(audit_path, record)
    return report


def save_pipeline_report(report: dict, path: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
