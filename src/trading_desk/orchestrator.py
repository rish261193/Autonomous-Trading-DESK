"""Deterministic local event router. No LLMs, network, broker, or side effects.

This is an integration skeleton, not autonomous agent intelligence.
"""
from __future__ import annotations
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from .agent_contracts import AgentEvent, AgentResponse, EventType, Role, validate_event

Handler = Callable[[AgentEvent], AgentResponse]

@dataclass(frozen=True)
class DispatchRecord:
    event_id: str
    event_type: EventType
    role: Role
    outcome: str

class Orchestrator:
    def __init__(self, max_events: int = 1000):
        if max_events < 1:
            raise ValueError("max_events must be positive")
        self._handlers: dict[tuple[EventType, Role], Handler] = {}
        self.max_events = max_events
        self.history: list[DispatchRecord] = []

    def subscribe(self, event_type: EventType, role: Role, handler: Handler) -> None:
        key = (event_type, role)
        if key in self._handlers:
            raise ValueError("Handler already registered")
        self._handlers[key] = handler

    def run(self, initial: AgentEvent) -> list[DispatchRecord]:
        validate_event(initial)
        queue = deque([initial])
        seen: set[str] = set()
        processed = 0
        while queue:
            event = queue.popleft()
            validate_event(event)
            if event.event_id in seen:
                continue
            seen.add(event.event_id)
            processed += 1
            if processed > self.max_events:
                raise RuntimeError("Event processing limit reached")
            for (event_type, role), handler in list(self._handlers.items()):
                if event_type is not event.event_type:
                    continue
                response = handler(event)
                if response.role is not role or response.event_id != event.event_id:
                    raise ValueError("Handler response identity mismatch")
                self.history.append(DispatchRecord(event.event_id, event.event_type,
                                                   role, response.outcome))
                for proposed in response.proposed_events:
                    validate_event(proposed)
                    # CRM cannot propose trading or risk decisions, even indirectly.
                    if role is Role.WHATSAPP_CRM and proposed.event_type in (
                        EventType.STRATEGY_AUTHORIZED,
                        EventType.ORDER_INTENT_PROPOSED,
                        EventType.RISK_DECISION_RECORDED,
                    ):
                        raise ValueError("CRM cannot initiate trading authority")
                    queue.append(proposed)
        return list(self.history)
