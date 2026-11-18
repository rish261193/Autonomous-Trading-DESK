"""Append-only JSONL research audit records (not an execution ledger)."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

def fingerprint(data: bytes) -> str:
    return sha256(data).hexdigest()

def make_experiment_record(strategy: str, parameters: dict, data_sha256: str,
                           results: dict, notes: str = "") -> dict:
    if not strategy or not data_sha256 or len(data_sha256) != 64:
        raise ValueError("strategy and 64-character data fingerprint required")
    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy": strategy,
        "parameters": parameters,
        "data_sha256": data_sha256,
        "results": results,
        "notes": notes,
        "status": "unverified_research",
    }

def append_jsonl(path: str, record: dict) -> None:
    """Local append-only-by-convention log; not tamper-proof or concurrent-safe."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
