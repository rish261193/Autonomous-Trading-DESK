# Autonomous Trading DESK

Research-first, risk-gated AI cryptocurrency trading desk. The goal is **sustainable net profitability after trading and operating costs**, demonstrated through reproducible research and paper trading before considering a subscription product.

## Current status — Phase 2 stabilization

**Not release-ready. No live trading. Phase 3 is blocked.**

GitHub Actions run [#85](https://github.com/rish261193/Autonomous-Trading-DESK/actions/runs/44366393363) passed **90 Python unit tests (0 failures, 0 errors)** on commit `4361ab4` (November 18, 2026). This verifies the tested code paths, **not** operational readiness or the absence of financial/security defects.

The earlier failing CI runs #63–#77 were followed by successful runs #78–#85. The failures included outdated tests after direct-entry removal and changed fill authorization. The full source-level audit and unresolved release gates are recorded in [Phase 2 independent audit](docs/PHASE2_INDEPENDENT_AUDIT.md).

## Independent audit (2026-11-18)

An independent full-system review of `53e0870` is in [docs/independent-audit/](docs/independent-audit/README.md). Summary: **not ready for unattended paper trading; no trading edge demonstrated.** On real 2018–2026 data the existing research baselines underperformed buy-and-hold out of sample. The audit branch fixes stop evaluation on ordinary marks, the caller-controlled clock, ledger tamper detection (hash-chained, replay-verified events), position attribution, kill-switch reliability under DB contention, and agent producer spoofing. Behaviour changes: `PersistentPaperDesk.mark()` now closes crossed stops, and a caller-supplied `now` must agree with the trusted clock. Open Critical findings are F-01 (caller-asserted authorization) and F-02 (unauthenticated prices).

## Operating constraints

| Control | Target |
| --- | --- |
| Instruments | BTC/USD and ETH/USD, spot only |
| Paper starting capital | USD 500 |
| Incremental operating budget | USD 30 |
| Leverage and short selling | Not permitted |
| Planned risk per trade | Up to 1% of equity |
| Daily loss threshold | 3% of day-start equity |
| Kill switch | Must prevent new entries |
| Trading hours | Crypto 24/7; UTC midnight is an accounting boundary, not forced liquidation |

**Important:** Stop-loss gaps, fees and execution slippage can cause realized losses above planned risk. Current paper fills do not model real exchange execution.

## Architecture

- **Research layer:** market signals, backtesting, rolling validation and audit/reporting tools.
- **Eleven specialist roles:** Market Intelligence, Technical Analyst, Quant Analyst, Fundamental Analyst, Bull Agent, Bear Agent, Portfolio Manager, Risk Controller, Execution Agent, Performance Auditor and WhatsApp CRM. The Strategy Research Lab is a workflow, not a twelfth role.
- **Independent deterministic risk gateway:** checks order constraints, portfolio exposure, daily losses, kill switch and authorization flags. It is not yet an independently authenticated production boundary.
- **Paper execution prototype:** SQLite-backed ledger, pending cash/risk reservations, idempotent order IDs, synthetic fills and synthetic stop processing.
- **WhatsApp CRM:** advisory interface only; no direct broker authority.

## Phase 2 code map

| Module | Responsibility |
| --- | --- |
| `src/trading_desk/gateway.py` | Deterministic order-risk decisions |
| `src/trading_desk/paper_desk.py` | In-memory portfolio accounting |
| `src/trading_desk/persistent_paper.py` | SQLite state, events, restart recovery and atomic stop mark/close |
| `src/trading_desk/pending_orders.py` | Reservations, duplicate-ID prevention, cancellations and synthetic fills |
| `src/trading_desk/paper_controller.py` | Strategy allowlist and caller-provided UTC observation validation |
| `src/trading_desk/paper_stops.py` | Synthetic stops at observed prices, including gaps |
| `tests/` | Python unit and regression tests |

## Run tests

From the repository root, with a compatible Python 3 environment and the project installed:

```bash
python -m pip install -e .
python -m compileall -q src tests
python -m unittest discover -s tests -v
```

GitHub Actions runs the Python unit-test workflow on pushes. A green run is necessary but **not sufficient** for Phase 2 approval.

## Phase 2 release blockers

1. Establish a trusted market-data and strategy-authorization boundary that untrusted code cannot forge or bypass, including at fill time.
2. Implement robust UTC daily-loss accounting across resets, restarts and overnight positions.
3. Add tamper-evident event integrity and portfolio/order reconciliation.
4. Validate concurrency, interruption recovery, stale observations, order duplication and stop-gap behavior with failure-injection tests.
5. Model realistic paper execution costs and fill outcomes (fees, spread, slippage, rejected/partial fills).
6. Integrate research signals into the guarded execution path and verify end-to-end enforcement.

See [Phase 2 ledger notes](docs/PHASE2_PAPER_LEDGER.md), [Phase 2 audit](docs/PHASE2_INDEPENDENT_AUDIT.md) and [original quality audit](docs/QUALITY_AUDIT_2026-11-18.md).

## Project phases

1. **Foundation and baseline quality:** repository, research primitives and initial tests.
2. **Risk-gated paper ledger:** implemented as a prototype; **stabilization and safety sign-off pending**.
3. **Event-driven specialist intelligence:** **not started / blocked** until Phase 2 release gates pass.
4. **End-to-end independent validation:** research correctness, realistic simulation, failure handling and economic viability.
5. **Extended paper trading and commercialization assessment:** only after verified reliability and net-positive evidence.

## Security and scope

No exchange keys, real-money orders or live trading are supported by this prototype. Never commit credentials, API keys or private customer data. Do not expose the SQLite database or internal paper-order APIs to untrusted strategies.

**Nothing here is evidence of a profitable trading strategy or a production-ready trading system.**
