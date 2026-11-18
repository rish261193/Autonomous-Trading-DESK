import unittest
from trading_desk.agent_contracts import AgentEvent, AgentResponse, EventType, Role
from trading_desk.orchestrator import Orchestrator

class OrchestratorTests(unittest.TestCase):
    def test_routes_event_to_subscribed_role(self):
        router = Orchestrator()
        def handler(event):
            return AgentResponse(Role.QUANT_ANALYST, event.event_id, "queued")
        router.subscribe(EventType.RESEARCH_REQUESTED, Role.QUANT_ANALYST, handler)
        history = router.run(AgentEvent(EventType.RESEARCH_REQUESTED, Role.MARKET_INTELLIGENCE))
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].role, Role.QUANT_ANALYST)

    def test_rejects_crm_trade_authority(self):
        router = Orchestrator()
        def handler(event):
            forbidden = AgentEvent(EventType.ORDER_INTENT_PROPOSED, Role.EXECUTION_AGENT)
            return AgentResponse(Role.WHATSAPP_CRM, event.event_id, "attempt",
                                 proposed_events=(forbidden,))
        router.subscribe(EventType.CLIENT_UPDATE_REQUESTED, Role.WHATSAPP_CRM, handler)
        with self.assertRaises(ValueError):
            router.run(AgentEvent(EventType.CLIENT_UPDATE_REQUESTED, Role.PERFORMANCE_AUDITOR))

    def test_rejects_invalid_authorization_producer(self):
        with self.assertRaises(ValueError):
            Orchestrator().run(AgentEvent(EventType.STRATEGY_AUTHORIZED, Role.BULL_AGENT))

    def test_rejects_duplicate_subscription(self):
        router = Orchestrator()
        handler = lambda e: AgentResponse(Role.QUANT_ANALYST, e.event_id, "ok")
        router.subscribe(EventType.RESEARCH_REQUESTED, Role.QUANT_ANALYST, handler)
        with self.assertRaises(ValueError):
            router.subscribe(EventType.RESEARCH_REQUESTED, Role.QUANT_ANALYST, handler)

    def test_event_budget(self):
        router = Orchestrator(max_events=2)
        def handler(event):
            return AgentResponse(Role.QUANT_ANALYST, event.event_id, "next",
                proposed_events=(AgentEvent(EventType.RESEARCH_REQUESTED, Role.QUANT_ANALYST),))
        router.subscribe(EventType.RESEARCH_REQUESTED, Role.QUANT_ANALYST, handler)
        with self.assertRaises(RuntimeError):
            router.run(AgentEvent(EventType.RESEARCH_REQUESTED, Role.MARKET_INTELLIGENCE))

if __name__ == "__main__":
    unittest.main()
