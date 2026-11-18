# Event-driven eleven-role orchestration

The desk has exactly eleven specialist roles. The Strategy Research Lab is a workflow that uses them, **not a twelfth role**.

The initial `agent_contracts.py` and `orchestrator.py` establish typed event messages, role identities, local subscriptions, bounded processing, and a narrow restriction against CRM-originated trade-authority events. These are **interface scaffolding**, not operational LLM agents or a secure authorization boundary.

## Intended research sequence

Market Intelligence identifies data availability and research opportunities. Technical, Quant, and Fundamental Analysts evaluate hypotheses and data quality. Bull and Bear Agents debate alternative market interpretations. Portfolio Manager proposes bounded strategy authorization only after validation. Risk Controller independently checks each proposed trade via the deterministic gateway. Execution Agent handles approved paper intents through a separate engine. Performance Auditor reviews reconciled outcomes. WhatsApp CRM communicates verified results and accepts authenticated user controls, without broker access.

## Important security boundary

An in-process event producer string is **not authentication**. The current router validates claimed roles but cannot prove which component created a message. The independent risk gateway must enforce permissions at the actual order boundary, using trusted authorization records, persistent state and broker reconciliation. Never treat event messages alone as permission to trade.

## Next build steps

Add tool capability registry and research-task handlers, persistent idempotent event storage, independent gateway enforcement, and end-to-end simulation. Introduce LLM providers only after deterministic tool contracts are useful and measurable.
