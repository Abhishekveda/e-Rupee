"""
orchestrator.py
===============
The e₹ Bridge AI Agent Orchestrator.

This is the entry point for all AI operations. It:
  1. Routes incoming requests to the correct sub-agent
  2. Combines outputs from multiple agents when needed
  3. Manages conversation state per session
  4. Provides a unified interface to the FastAPI layer

AGENT ROUTING LOGIC:
====================
  classify_purpose() → FEMAAgent
  score_risk()        → RiskAgent
  answer_question()   → QAAgent
  full_pre_check()    → FEMAAgent + RiskAgent (combined)

SESSION MANAGEMENT:
===================
  Conversation history is stored in memory (dict keyed by session_id).
  In production, this would be persisted in Redis or PostgreSQL.
  Max 20 messages per session (10 exchanges) to prevent memory bloat.
"""

from app.agent.fema_agent import FEMAAgent
from app.agent.risk_agent import RiskAgent
from app.agent.qa_agent import QAAgent


class AgentOrchestrator:
    """
    Central orchestrator for the e₹ Bridge AI agent system.

    All three sub-agents are initialised once at startup and reused
    across requests (thread-safe for read operations).
    """

    def __init__(self):
        self.fema_agent = FEMAAgent()
        self.risk_agent = RiskAgent()
        self.qa_agent = QAAgent()
        self._sessions: dict[str, list] = {}
        print("[e₹ Agent] Orchestrator initialised — FEMA, Risk, QA agents ready.")

    # ── Public interface ──────────────────────────────────────────────────────

    def classify_purpose(self, description: str, amount_inr: float) -> dict:
        """Route to FEMA classification agent."""
        return self.fema_agent.classify(description, amount_inr)

    def score_risk(
        self,
        sender_wallet: str,
        recipient_address: str,
        amount_inr: float,
        purpose_code: str,
        recipient_country: str,
        transfer_history: list = None,
    ) -> dict:
        """Route to risk scoring agent."""
        return self.risk_agent.score(
            sender_wallet=sender_wallet,
            recipient_address=recipient_address,
            amount_inr=amount_inr,
            purpose_code=purpose_code,
            recipient_country=recipient_country,
            transfer_history=transfer_history or [],
        )

    def answer_question(self, question: str, session_id: str = "default") -> dict:
        """Route to Q&A agent, maintaining conversation context."""
        history = self._sessions.get(session_id, [])
        result = self.qa_agent.answer(question, conversation_context=history)

        # Update conversation history
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": result["answer"]})
        self._sessions[session_id] = history[-20:]  # keep last 10 exchanges

        return result

    def pre_transfer_check(
        self,
        description: str,
        sender_wallet: str,
        recipient_address: str,
        amount_inr: float,
        purpose_code: str,
        recipient_country: str,
        transfer_history: list = None,
    ) -> dict:
        """
        Combined pre-flight check: FEMA classification + risk scoring.
        Called just before a transfer is executed.
        Returns a unified assessment.
        """
        fema = self.fema_agent.classify(description or "", amount_inr)
        risk = self.risk_agent.score(
            sender_wallet, recipient_address, amount_inr,
            purpose_code, recipient_country, transfer_history or []
        )

        # Overall recommendation
        if risk["recommendation"] == "BLOCK":
            overall = "BLOCK"
        elif risk["recommendation"] == "REVIEW" or fema["confidence"] == "LOW":
            overall = "REVIEW"
        else:
            overall = "APPROVE"

        return {
            "overall_recommendation": overall,
            "fema_analysis": fema,
            "risk_analysis": risk,
            "combined_summary": (
                f"FEMA: {fema['code']} ({fema['confidence']} confidence). "
                f"Risk: {risk['risk_level']} (score: {risk['risk_score']}/100). "
                f"Recommendation: {overall}."
            ),
        }

    def get_status(self) -> dict:
        """Health check — returns agent status."""
        return {
            "status": "operational",
            "agents": {
                "fema_agent": {
                    "status": "ready",
                    "codes_indexed": len(self.fema_agent.code_order),
                    "method": "TF-IDF + keyword matching",
                },
                "risk_agent": {
                    "status": "ready",
                    "rules": 8,
                    "method": "Rule-based scoring",
                },
                "qa_agent": {
                    "status": "ready",
                    "knowledge_chunks": len(self.qa_agent.chunk_ids),
                    "method": "RAG" + (" + Groq Llama 3.1" if self.qa_agent._groq_client else " (retrieval-only)"),
                    "groq_enabled": self.qa_agent._groq_client is not None,
                },
            },
            "sessions_active": len(self._sessions),
            "version": "1.0.0",
        }
