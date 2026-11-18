# 07 — Agent architecture review

## Current state

**No agent is implemented.** `agent_contracts.py` defines 11 `Role` enums and 12 `EventType`s. `orchestrator.py` is a synchronous in-memory router with no handlers, no LLM client, no persistence and no connection to `PendingOrders`. `tools.py` exposes three SMA research tools behind self-declared role strings. Deferring LLM integration was the right call (`docs/AGENT_EVENTS.md`: "Introduce LLM providers only after deterministic tool contracts are useful and measurable"). The 11-role design should now be cut down before anyone builds it.

## Role-by-role evaluation

Cost assumptions: per-call cost = 4k input + 1k output tokens. Third-party-reported OpenAI list prices (not verified at source): GPT-6 Luna $0.10/$0.50, Sol $2/$10, Astra $10/$50 per million tokens. That gives about $0.0009, $0.018 and $0.09 per call. Frequencies are my recommendation.

| # | Role | Actual purpose | LLM needed? | Better as | Frequency | Est. cost/mo | Main failure modes | Contributes to P&L? | Recommendation |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Market Intelligence | Scan news and regime for hypotheses | Partly (summarization) | LLM over a fixed news feed, *offline* | Daily | $0.03–$2.70 | Hallucinated events, stale news, narrative bias | Indirect at best; no evidence | **Merge** into Research Assistant |
| 2 | Technical Analyst | Interpret indicators | **No**: indicators are arithmetic | Deterministic signal code | Per bar (no LLM) | $0 | LLM misreads numbers it could compute | Only via validated signals | **Replace** with code |
| 3 | Quantitative Analyst | Design and run experiments | Partly (proposing hypotheses, writing specs) | Deterministic pipeline + LLM helper for specs | Weekly batch | <$1–$5 | p-hacking at machine speed; unlimited configs → selection bias | Yes, *if* bound by the validation framework (`04`) | **Keep** as Research Assistant, with a hard budget on configs tested |
| 4 | Fundamental Analyst | Macro and crypto fundamentals | Partly | Same as #1 | Weekly | ≈$0 | Unfalsifiable narratives | No measurable link for BTC/ETH daily-intraday | **Merge** into #1 or drop |
| 5 | Bull Agent | Argue for long | Yes (by construction) | — | Per decision | $0.05–$130 (both agents) | Artificial confidence, verbosity; both sides read the same data | **No evidence.** Debate between two prompts over identical inputs adds no information, only variance and cost | **Drop** |
| 6 | Bear Agent | Argue against | Yes | — | Per decision | same | same | same | **Drop**; replace with a deterministic pre-mortem checklist (regime, liquidity, drawdown state) |
| 7 | Portfolio Manager | Rank opportunities within limits | **No** for sizing/selection (rules); maybe for explanations | Deterministic allocator over approved strategies | Per signal (no LLM) | $0 | LLM overriding validated rules | Yes, but only as code | **Replace** with code |
| 8 | Risk Controller | Enforce limits | **Must not** be an LLM | Deterministic gateway + watchdog (exists) | Every order | $0 | An LLM can be persuaded | Protective | **Deterministic only.** An optional LLM may *explain* rejections, never decide |
| 9 | Execution Agent | Place and reconcile orders | **No** | Deterministic adapter | Every order | $0 | Retries, duplicates, hallucinated fills | Protective | **Replace** with code |
| 10 | Performance Auditor | Attribution and reconciliation | **No** for numbers; LLM for narrative | Deterministic report + LLM summary | Daily | $0.03–$2.70 | LLM misreporting numbers | Indirect (kills bad strategies) | **Code** + optional LLM summary of verified numbers |
| 11 | WhatsApp RM | Communicate; accept operator commands | Yes (conversation) | LLM with read-only ledger API; only command = halt request, authenticated | On demand | messaging fees (`08`) + $0.1–$3 | Prompt injection via inbound messages; impersonation | No | **Keep later** (Phase 5). Advisory only; must never reach reserve/fill. A halt request should only *raise* safety. |

Cost range = Luna to Astra at the stated frequency. The Bull/Bear range assumes both agents at 1 decision/day on Luna (low) up to hourly debates on Astra (high). The arithmetic is in `08`.

## Specific questions

**Do Bull and Bear agents improve decisions?** Nothing in the repo or the literature it cites supports it for systematic BTC/ETH trading. Both agents see the same inputs and produce persuasive text, not new information. If the PM is a rule, debate can't change the outcome. If the PM is an LLM, debate adds a path for the most eloquent argument, not the best-evidenced one, to win. The useful part of "Bear" is a falsification checklist, and that is better as deterministic pre-trade checks.

**Should the Risk Controller be an AI agent?** No. Enforcement must be deterministic, non-negotiable and outside any LLM's write path, which is what `gateway.authorize` already is. An LLM "risk commentator" that reads gateway decisions and explains them is harmless and optional. The two must not share a name, because "Risk Controller (agent)" invites someone to wire it into the approval path.

**Unnecessary communication?** The 12 event types describe a pipeline where 6+ agents pass messages per trade decision. For a system whose orders should come from a validated deterministic rule, that chain adds latency, cost and failure modes with no measurable benefit.

## Leanest viable agent architecture

| Component | Type | Authority |
|---|---|---|
| **Research Assistant** (merges 1, 3, 4) | LLM, offline, weekly | Proposes strategy specs + evidence packs. Can call research tools. Cannot touch the registry or ledger. |
| **Signal & Allocation Engine** (replaces 2, 7, 9) | Deterministic | Runs only human-approved, versioned strategies. |
| **Gateway & Watchdog** (8) | Deterministic | Sole order authority; auto-halt. |
| **Auditor** (10) | Deterministic + optional LLM narrative | Read-only. |
| **Communicator** (11) | LLM, later | Read-only + authenticated halt request. |

That is two LLM components instead of eleven, and LLM calls fall from per decision to per week plus on demand.
