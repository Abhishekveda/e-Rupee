"""
orchestrator.py
---------------
Central router for all five e₹ Bridge AI agents.

  1. FEMA Agent       — purpose code classification
  2. Risk Agent       — pre-transfer fraud/compliance scoring
  3. Q&A Agent        — regulatory knowledge base (RAG)
  4. Customer Agent   — account-aware query resolution
  5. Speed Agent      — route and timing optimisation
"""

from app.agent.fema_agent import FEMAAgent
from app.agent.risk_agent import RiskAgent
from app.agent.qa_agent import QAAgent
from app.agent.customer_agent import CustomerAgent
from app.agent.speed_agent import SpeedAgent


class AgentOrchestrator:

    def __init__(self):
        self.fema_agent     = FEMAAgent()
        self.risk_agent     = RiskAgent()
        self.qa_agent       = QAAgent()
        self.customer_agent = CustomerAgent()
        self.speed_agent    = SpeedAgent()
        self._sessions: dict[str, list] = {}
        print("[e₹ Agent] All 5 agents initialised.")

    def classify_purpose(self, description: str, amount_inr: float) -> dict:
        return self.fema_agent.classify(description, amount_inr)

    def score_risk(self, sender_wallet, recipient_address, amount_inr,
                   purpose_code, recipient_country, transfer_history=None) -> dict:
        return self.risk_agent.score(
            sender_wallet=sender_wallet,
            recipient_address=recipient_address,
            amount_inr=amount_inr,
            purpose_code=purpose_code,
            recipient_country=recipient_country,
            transfer_history=transfer_history or [],
        )

    def answer_question(self, question: str, session_id: str = "default") -> dict:
        history = self._sessions.get(session_id, [])
        result = self.qa_agent.answer(question, history)
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": result["answer"]})
        self._sessions[session_id] = history[-20:]
        return result

    def answer_customer(self, question: str, user_context=None, tx_context=None) -> dict:
        return self.customer_agent.answer(question, user_context, tx_context)

    def recommend_route(self, source_country, dest_country, amount_inr, urgency="normal") -> dict:
        return self.speed_agent.recommend_route(source_country, dest_country, amount_inr, urgency)

    def recommend_timing(self, source_currency, dest_currency) -> dict:
        return self.speed_agent.recommend_timing(source_currency, dest_currency)

    def pre_transfer_check(self, description, sender_wallet, recipient_address,
                            amount_inr, purpose_code, recipient_country, transfer_history=None) -> dict:
        fema = self.fema_agent.classify(description or "", amount_inr)
        risk = self.risk_agent.score(
            sender_wallet, recipient_address, amount_inr,
            purpose_code, recipient_country, transfer_history or []
        )
        route = self.speed_agent.recommend_route(
            "IN", recipient_country[:2].upper(), amount_inr
        )
        overall = "BLOCK" if risk["recommendation"] == "BLOCK" else \
                  "REVIEW" if risk["recommendation"] == "REVIEW" or fema["confidence"] == "LOW" else "APPROVE"
        return {
            "overall_recommendation": overall,
            "fema_analysis": fema,
            "risk_analysis": risk,
            "route_recommendation": route,
            "summary": (
                f"FEMA: {fema['code']} ({fema['confidence']} confidence). "
                f"Risk: {risk['risk_level']} (score {risk['risk_score']}/100). "
                f"Route: {route['recommended_route']['label']}. "
                f"Decision: {overall}."
            ),
        }

    def get_status(self) -> dict:
        return {
            "status": "operational",
            "agents": {
                "fema_agent":     {"status": "ready", "codes_indexed": len(self.fema_agent.code_order)},
                "risk_agent":     {"status": "ready", "rules": 8},
                "qa_agent":       {"status": "ready", "knowledge_chunks": len(self.qa_agent.chunk_ids),
                                   "groq_enabled": self.qa_agent._groq_client is not None},
                "customer_agent": {"status": "ready", "intents": 8},
                "speed_agent":    {"status": "ready", "corridors": 12},
            },
            "total_agents": 5,
            "version": "2.0.0",
        }
