"""Time-series split design and guardrails against data leakage."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Split:
    train_start: int
    train_end: int
    test_start: int
    test_end: int

def rolling_splits(total: int, train_size: int, test_size: int, gap: int = 0,
                   step: int | None = None) -> list[Split]:
    """Generate fixed-width rolling windows; end indices are exclusive.

    Gap represents an embargo between train and test. It is not a replacement
    for event-label purging or other leakage controls.
    """
    if total <= 0 or train_size <= 0 or test_size <= 0 or gap < 0:
        raise ValueError("Invalid split sizes")
    stride = test_size if step is None else step
    if stride <= 0:
        raise ValueError("step must be positive")
    out = []
    train_start = 0
    while train_start + train_size + gap + test_size <= total:
        train_end = train_start + train_size
        test_start = train_end + gap
        out.append(Split(train_start, train_end, test_start, test_start + test_size))
        train_start += stride
    if not out:
        raise ValueError("Not enough data for one split")
    return out
