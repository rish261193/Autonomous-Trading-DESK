"""Allowlisted research tool registry with typed input validation.

Tools are deterministic and side-effect-free by default. No broker functions.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable
from typing import Any
from .research import Bar, Costs, backtest, grid_search, validate_bars
from .strategies import sma_hypotheses

@dataclass(frozen=True)
class ToolResult:
    tool: str
    success: bool
    output: Any
    error: str | None = None

@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: Callable[[dict[str, Any]], Any]
    allowed_roles: frozenset[str]
    version: int = 1

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not spec.name or spec.version < 1 or not spec.allowed_roles:
            raise ValueError("Invalid tool specification")
        if spec.name in self._tools:
            raise ValueError("Tool already registered")
        self._tools[spec.name] = spec

    def catalog(self, role: str) -> list[dict[str, Any]]:
        return [{"name": t.name, "description": t.description, "version": t.version}
                for t in self._tools.values() if role in t.allowed_roles]

    def invoke(self, name: str, role: str, arguments: dict[str, Any]) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None:
            return ToolResult(name, False, None, "Unknown tool")
        if role not in spec.allowed_roles:
            return ToolResult(name, False, None, "Role not permitted")
        if not isinstance(arguments, dict):
            return ToolResult(name, False, None, "Arguments must be a dictionary")
        try:
            return ToolResult(name, True, spec.handler(arguments))
        except (ValueError, TypeError, KeyError) as exc:
            return ToolResult(name, False, None, f"Invalid tool request: {exc}")

def _get_bars(args: dict[str, Any]) -> list[Bar]:
    bars = args["bars"]
    if not isinstance(bars, list) or not all(isinstance(b, Bar) for b in bars):
        raise TypeError("bars must be a list of Bar objects")
    validate_bars(bars)
    return bars

def _sma_candidates(args: dict[str, Any]) -> list[dict[str, Any]]:
    fast = args["fast_windows"]
    slow = args["slow_windows"]
    if not isinstance(fast, list) or not isinstance(slow, list):
        raise TypeError("windows must be lists")
    if len(fast) * len(slow) > 10000:
        raise ValueError("maximum 10000 candidate combinations")
    return [{"id": x.identifier, "family": x.family, "parameters": dict(x.parameters)}
            for x in sma_hypotheses(fast, slow)]

def _sma_backtest(args: dict[str, Any]) -> dict[str, Any]:
    from dataclasses import asdict
    bars = _get_bars(args)
    fast, slow = args["fast"], args["slow"]
    if not isinstance(fast, int) or isinstance(fast, bool) or not isinstance(slow, int) or isinstance(slow, bool):
        raise TypeError("fast and slow must be integers")
    costs = Costs(args.get("fee_bps", 10.0), args.get("slippage_bps", 5.0))
    return asdict(backtest(bars, fast, slow, costs))

def _sma_grid(args: dict[str, Any]) -> list[dict[str, Any]]:
    from dataclasses import asdict
    bars = _get_bars(args)
    fast = args["fast_windows"]
    slow = args["slow_windows"]
    if not isinstance(fast, list) or not isinstance(slow, list):
        raise TypeError("windows must be lists")
    if len(fast) * len(slow) > 10000:
        raise ValueError("maximum 10000 candidate combinations")
    costs = Costs(args.get("fee_bps", 10.0), args.get("slippage_bps", 5.0))
    return [asdict(x) for x in grid_search(bars, fast, slow, costs)]

def build_research_registry() -> ToolRegistry:
    registry = ToolRegistry()
    analysts = frozenset({"quant_analyst", "technical_analyst"})
    registry.register(ToolSpec("research.sma_candidates",
                               "Generate long-only SMA research hypotheses",
                               _sma_candidates, analysts))
    registry.register(ToolSpec("research.sma_backtest",
                               "Evaluate one SMA configuration with simplified costs",
                               _sma_backtest, analysts))
    registry.register(ToolSpec("research.sma_grid",
                               "Rank SMA configurations on provided historical bars",
                               _sma_grid, frozenset({"quant_analyst"})))
    return registry
