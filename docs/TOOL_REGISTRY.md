# Research tool capability registry

The first version provides a common allowlisted interface to deterministic research functions:

| Tool | Allowed roles | Function |
| --- | --- | --- |
| `research.sma_candidates` | Technical Analyst, Quant Analyst | Generate SMA configurations |
| `research.sma_backtest` | Technical Analyst, Quant Analyst | Backtest one configuration |
| `research.sma_grid` | Quant Analyst | Screen configurations |

The registry exposes a role-filtered catalog, checks tool names and role allowlists, validates arguments in handlers, and returns structured outcomes. It contains **no broker or trade execution functions**.

## Security limitations

Role strings supplied to `invoke` are not authenticated. The allowlist is an orchestration guardrail, **not a security boundary**. Production systems must derive role identity from a trusted runtime and enforce the independent deterministic risk gateway at the order boundary. Handler exceptions outside common validation failures currently propagate and need centralized fault handling and resource isolation.

## Planned extensions

Introduce provider adapters for verified market-data sources, alternative strategy families, parameter optimization and realistic event-based simulation. Keep tools independently testable and avoid per-tick LLM calls.
