"""Typed messages for the approved eleven-role architecture.

Agents may propose research and bounded strategies. No role may place orders
or override the deterministic risk gateway.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

class Role(str, Enum):
    MARKET_INTELLIGENCE = "market_intelligence"
    TECHNICAL_ANALYST = "technical_analyst"
    QUANT_ANALYST = "quant_analyst"
    FUNDAMENTAL_ANALYST = "fundamental_analyst"
    BULL_AGENT = "bull_agent"
    BEAR_AGENT = "bear_agent"
    PORTFOLIO_MANAGER = "portfolio_manager"
    RISK_CONTROLLER = "risk_controller"
    EXECUTION_AGENT = "execution_agent"
    PERFORMANCE_AUDITOR = "performance_auditor"
    WHATSAPP_CRM = "whatsapp_crm"

class EventType(str, Enum):
    MARKET_DATA_READY = "market_data_ready"
    RESEARCH_REQUESTED = "research_requested"
    HYPOTHESIS_PROPOSED = "hypothesis_proposed"
    BACKTEST_COMPLETED = "backtest_completed"
    VALIDATION_COMPLETED = "validation_completed"
    STRATEGY_REVIEW_REQUESTED = "strategy_review_requested"
    STRATEGY_AUTHORIZED = "strategy_authorized"
    ORDER_INTENT_PROPOSED = "order_intent_proposed"
    RISK_DECISION_RECORDED = "risk_decision_recorded"
    PAPER_FILL_RECORDED = "paper_fill_recorded"
    AUDIT_COMPLETED = "audit_completed"
    CLIENT_UPDATE_REQUESTED = "client_update_requested"

@dataclass(frozen=True)
class AgentEvent:
    event_type: EventType
    producer: Role
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlation_id: str | None = None

@dataclass(frozen=True)
class AgentResponse:
    role: Role
    event_id: str
    outcome: str
    evidence: tuple[str, ...] = ()
    proposed_events: tuple[AgentEvent, ...] = ()

def validate_event(event: AgentEvent) -> None:
    if not isinstance(event.event_type, EventType) or not isinstance(event.producer, Role):
        raise ValueError("Invalid role or event type")
    if not isinstance(event.payload, dict) or not event.event_id:
        raise ValueError("Invalid event")
    if event.event_type is EventType.STRATEGY_AUTHORIZED and event.producer is not Role.PORTFOLIO_MANAGER:
        raise ValueError("Only portfolio manager can propose strategy authorization")
    if event.event_type is EventType.RISK_DECISION_RECORDED and event.producer is not Role.RISK_CONTROLLER:
        raise ValueError("Risk decisions must be recorded by risk controller")
    if event.event_type is EventType.ORDER_INTENT_PROPOSED and event.producer is not Role.EXECUTION_AGENT:
        raise ValueError("Order intents must be proposed by execution agent")
    if event.event_type is EventType.CLIENT_UPDATE_REQUESTED and event.producer not in (Role.PERFORMANCE_AUDITOR, Role.WHATSAPP_CRM):
        raise ValueError("Client updates must originate from auditor or CRM")
