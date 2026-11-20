# Autonomous Trading DESK

**Research-first, multi-agent cryptocurrency paper-trading laboratory.** Built to test whether AI-assisted strategies can generate repeatable **net returns after fees, spread, slippage, and operating costs**—without giving agents direct authority over capital or the risk ledger.

> **Status (18 November 2026): Phase 2 security integration in progress. NOT production-ready, NOT cleared for unattended trading, and NO live-money execution.** The integration branch contains additional controls that have **not yet passed its latest GitHub Actions CI run**. No profitable trading edge has been demonstrated.

[Integration PR #4](https://github.com/rish261193/Autonomous-Trading-DESK/pull/4) · [GitHub Actions](https://github.com/rish261193/Autonomous-Trading-DESK/actions) · [Independent audit](docs/independent-audit/README.md) · [Finding-by-finding review](docs/CLAUDE_FINDINGS_DECISION_REVIEW.md) · [Security boundary notes](docs/PAPER_INTENT_BOUNDARY.md)

## Mission and operating philosophy

Build a lean, reproducible autonomous research and **paper-only** trading desk. Agents may generate signals and trade *intents*; an independently controlled deterministic risk gateway must decide what is permissible. Capital preservation, provenance, failure isolation, and auditability take priority over apparent model confidence. Results must be measured out of sample, with realistic execution costs and against simple benchmarks.

This is an experimental software project, **not investment advice**, a broker, or a verified profitable strategy.

## Project profile

| Attribute | Description |
| --- | --- |
| Project | Autonomous Trading DESK |
| Repository | [rish261193/Autonomous-Trading-DESK](https://github.com/rish261193/Autonomous-Trading-DESK) |
| Maintainer | **Rishabh Sinha** |
| Maintainer background | Toronto-based enterprise technology and AI builder; works in B2B enterprise technology and builds lean AI products independently |
| Focus | Multi-agent research, quantitative validation, deterministic risk controls, resilient paper execution |
| Primary language | Python 3.11 / 3.13 |
| Storage | SQLite-backed paper ledger and event log |
| Market scope | BTC/USD and ETH/USD spot |
| Execution mode | Synthetic/paper only |
| Broker keys | None required or supported in this prototype |
| Deployment | Local prototype; isolated production-like paper deployment not complete |
| Cost principle | Prefer open-source software and public market data; avoid unnecessary paid infrastructure |
| Development approach | Small auditable commits, independent review, adversarial tests, CI before merging |

## Risk policy

| Control | Target / current constraint |
| --- | --- |
| Starting paper equity | **USD $500** |
| Incremental tooling budget | **USD $30** |
| Instruments | BTC/USD and ETH/USD only |
| Product | Spot only; no leverage, margin, or shorting |
| Planned position risk | At most 1% of equity per trade, subject to aggregate risk limits |
| Daily loss threshold | 3% of day-start equity |
| Kill switch | Persistent stop for new trading entries; operator-controlled recovery |
| Accounting clock | UTC; midnight rolls the daily accounting boundary, not positions |
| Trade authority | Agents propose; trusted service and deterministic risk logic decide |

**Risk limitations:** A stop price is not a guaranteed execution price. Gaps, stale quotes, spread, fees, slippage, and outages can produce losses exceeding the intended risk. Current synthetic fills are not a realistic exchange execution model.

## Architecture at a glance

```text
Research / market intelligence / strategy agents
                   |
             Trade intent only
                   |
       Authenticated paper-intent API
                   |
        Trusted owner-side service
                   |
  Independent price corroboration (prototype)
                   |
   Market-data circuit breaker (prototype)
                   |
     Deterministic risk / order gateway
                   |
     Reservations + synthetic fills
                   |
    Persistent SQLite ledger + audit log
                   |
      Persistent .HALT kill-switch flag
```

**Trust boundary:** This diagram is the intended composition, not proof of deployed process isolation. The HTTP endpoint uses HMAC request authentication, a timestamp window, and an in-memory nonce replay cache. Agents must ultimately run without direct access to the database, secret material, or owner-only APIs. Until that isolation is implemented, the critical authorization and price-forgery findings remain open.

### Specialist-agent concept

The intended roles are **Market Intelligence, Technical Analyst, Quant Analyst, Fundamental Analyst, Bull Agent, Bear Agent, Portfolio Manager, Risk Controller, Execution Agent, Performance Auditor, and WhatsApp CRM**. The Strategy Research Lab is a workflow rather than a twelfth agent. **Listing a role does not mean an independently deployed agent exists.** WhatsApp is deferred: no WhatsApp integration, remote HALT command, or WhatsApp alert delivery is currently implemented.

## Implemented components and limitations

| Component | File | Current reality |
| --- | --- | --- |
| Deterministic risk gateway | `src/trading_desk/gateway.py` | Risk checks; not an OS-enforced security boundary |
| Paper portfolio | `src/trading_desk/paper_desk.py` | Synthetic positions, marks, stops and accounting |
| Persistent ledger | `src/trading_desk/persistent_paper.py` | SQLite state, event hash chain, replay checks, restart recovery, `.HALT` flag |
| Reservations | `src/trading_desk/pending_orders.py` | Order IDs, cash/risk reservations and synthetic fills; direct caller authorization remains a security concern |
| Guarded controller | `src/trading_desk/paper_controller.py` | Strategy allowlist and timestamp checks |
| Trusted intents | `src/trading_desk/trusted_paper_intents.py` | Agents submit intent fields, not caller-asserted prices or authorization |
| HMAC HTTP boundary | `src/trading_desk/paper_intent_http.py` | Local paper-intent endpoint; not deployed or OS-isolated |
| Kraken public ticker | `src/trading_desk/kraken_public_prices.py` | Public REST prices; **receipt time is not exchange event time** |
| Two-source quote check | `src/trading_desk/corroborated_prices.py` | Freshness, symbol, agreement, and timestamp-regression validation; independent production adapters missing |
| Feed circuit breaker | `src/trading_desk/market_data_breaker.py` | Trips on consecutive quote errors; can call persistent ledger halt |
| Owner-side safety composition | `src/trading_desk/paper_safety_composition.py` | Wires quote corroboration, circuit breaker, persistent halt, and trusted intent service; not deployed |
| Adversarial tests | `tests/` | Regression and security tests, including documented expected failures for unresolved findings |

**Kill-switch semantics:** Repeated failed price requests can trip the breaker and call the ledger's persistent halt. The `.HALT` file is checked on ledger restart. This does **not** yet detect a silent feed outage when no requests are made; an independent heartbeat/watchdog is still required. The breaker's owner reset does **not** clear the persistent ledger halt.

## Quick start: local tests

Requires Python 3.11+ and Git. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m compileall -q src tests
python -m unittest discover -s tests -v
```

On Windows, activate with `.venv\\Scripts\\activate` instead.

These commands run offline unit tests; they do **not** launch an autonomous trading desk. Do not expose the local paper-intent HTTP service to the internet, share its HMAC secret with strategy processes, or provide agents write access to the SQLite ledger.

## CI and quality gates

The [Python unit-test workflow](.github/workflows/tests.yml) tests Python **3.11** and **3.13**. The integration workflow was changed to run **once per pull-request update**, rather than duplicating every push and PR run; pushes to `main` remain covered. Concurrency settings cancel superseded PR runs.

**Verification status:** Earlier baseline workflows passed, but the most recent integration runs were still queued at the last check. A previously observed failure was caused by tests not supplying the newly required HMAC secret; a matching test fix has been committed. **Do not describe the latest integration branch as green until both matrix jobs pass.** Some adversarial tests are intentionally marked expected-failure; a green workflow does not close their findings.

## Independent audit and release blockers

The independent audit of the earlier baseline is documented in [docs/independent-audit/](docs/independent-audit/README.md), with decisions tracked in [docs/CLAUDE_FINDINGS_DECISION_REVIEW.md](docs/CLAUDE_FINDINGS_DECISION_REVIEW.md).

**Highest-priority unresolved issues:**

1. **F-01: authorization bypass.** Enforce strategy/owner separation using distinct processes, authenticated IPC and database filesystem permissions. HMAC alone is not sufficient if untrusted agents possess owner secrets or ledger access.
2. **F-02: price integrity.** Integrate genuinely independent, exchange-event-timestamped quote sources; reject forged, stale, implausible, regressing, or disagreeing observations.
3. **Operational watchdog.** Detect silent feed outages independently of incoming trade requests and persistently halt new entries.
4. **Execution realism.** Add spread, fees, slippage, precision/minimum-size rules, partial fills, and reservation expiry.
5. **Accounting and reliability.** Verify loss limits across UTC rollovers, crashes, restarts, open positions, and failed writes. Externally anchor audit-chain heads if tamper resistance is required.
6. **End-to-end validation.** Test the complete strategy-intent-to-risk-to-paper-fill path under normal and adversarial conditions before unattended paper operation.
7. **Research validity.** Demonstrate out-of-sample net performance against buy-and-hold and other baselines. Earlier audit research did **not** demonstrate a profitable edge.

## Roadmap

| Stage | Status | Exit criteria |
| --- | --- | --- |
| 1. Research foundation | Prototype implemented | Reproducible tests and baseline tools |
| 2. Risk-gated persistent paper ledger | **Security hardening in progress** | Verified owner boundary, credible prices, watchdog, execution and accounting tests |
| 3. Event-driven specialist intelligence | **Blocked** | Phase 2 safety sign-off |
| 4. Independent end-to-end validation | **Pending** | Reproducible realistic evaluation, failure injection, benchmark comparisons |
| 5. Extended paper trial | **Pending** | Stable unattended paper operation and measured costs |
| 6. Commercialization assessment | **Exploratory only** | Evidence of reliability and net economic value |

See [architecture](docs/ARCHITECTURE.md), [roadmap](docs/ROADMAP.md), [research lab](docs/RESEARCH_LAB.md), [paper ledger](docs/PHASE2_PAPER_LEDGER.md), and [security boundary](docs/PAPER_INTENT_BOUNDARY.md).

## Security and contribution principles

- **Paper trading only.** No exchange order placement, leverage, or real-money execution is authorized.
- Keep credentials and personal data out of commits, logs, fixtures, and agent prompts.
- Never expose the SQLite database, owner secret, halt-reset mechanism, or privileged order APIs to untrusted agents.
- Treat agent outputs, market data, and research claims as untrusted inputs.
- Require regression tests for security fixes and verify both CI matrix versions before merging.
- Preserve independent audit findings, including unresolved expected-failure tests; do not mark a finding fixed merely because a module exists.
- Keep `main` stable; security integration work is tracked in [Draft PR #4](https://github.com/rish261193/Autonomous-Trading-DESK/pull/4).

---

**Maintained by Rishabh Sinha.** Enterprise technology professional and independent AI builder focused on practical, low-cost systems and transparent experimentation. This project documents the process of building, testing, and auditing an AI-assisted trading desk—not a claim of investment performance.
