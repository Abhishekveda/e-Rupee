"""
orchestrator.py
---------------
Entry point for the e₹ Bridge AI agent system.

Ties together the ReAct loop, security filter, memory manager,
and sub-agents into a single coherent interface.

All external calls (from main.py) go through this class.
"""

from app.agent.fema_agent import FEMAAgent
from app.agent.risk_agent import RiskAgent
from app.agent.qa_agent import QAAgent
from app.agent.core.react_loop import ReactLoop
from app.agent.core.memory import MemoryManager
from app.agent.security.security import SecurityFilter


class AgentOrchestrator:

    def __init__(self):
        # Sub-agents (direct tool access)
        self.fema = FEMAAgent()
        self.risk = RiskAgent()
        self.qa = QAAgent()
        # Agentic infrastructure
        self.react = ReactLoop()
        self.memory = MemoryManager()
        self.security = SecurityFilter()
        print(f"[e₹ Agent] Orchestrator ready — mode: {self.react.mode}")

    # ── Direct tool calls (fast path) ────────────────────────────────────────

    def classify_purpose(self, description: str, amount_inr: float) -> dict:
        return self.fema.classify(description, amount_inr)

    def score_risk(self, sender_wallet, recipient_address, amount_inr,
                   purpose_code, recipient_country, transfer_history=None) -> dict:
        return self.risk.score(
            sender_wallet=sender_wallet,
            recipient_address=recipient_address,
            amount_inr=amount_inr,
            purpose_code=purpose_code,
            recipient_country=recipient_country,
            transfer_history=transfer_history or [],
        )

    def answer_question(self, question: str, session_id: str = "default") -> dict:
        history = self.memory.get_history(session_id)
        result = self.qa.answer(question, conversation_context=history)
        self.memory.add_turn(session_id, question, result["answer"])
        return result

    def pre_transfer_check(self, description, sender_wallet, recipient_address,
                           amount_inr, purpose_code, recipient_country,
                           transfer_history=None) -> dict:
        fema = self.fema.classify(description or "", amount_inr)
        risk = self.risk.score(
            sender_wallet, recipient_address, amount_inr,
            purpose_code, recipient_country, transfer_history or []
        )
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

    # ── Agentic path (complex multi-step queries) ─────────────────────────────

    def run_agent(self, query: str, context: dict = None,
                  session_id: str = "default") -> dict:
        """
        Full ReAct agent loop for complex queries.
        Includes security filtering, memory injection, and reasoning trace.
        """
        # Security check
        sec = self.security.check(query, session_id)
        if not sec["allowed"]:
            return {
                "answer": f"Request blocked: {sec['threat_detail']}",
                "threat_detected": True,
                "threat_type": sec["threat_type"],
                "steps": [],
                "audit_hash": sec["audit_hash"],
            }

        clean_query = sec["clean_text"]

        # Inject memory context
        ctx = context or {}
        ctx["conversation_history"] = self.memory.get_history(session_id)

        # Run agent
        result = self.react.run(clean_query, ctx, session_id)

        # Store to memory
        self.memory.add_turn(session_id, clean_query, result.answer[:500])

        # Log the interaction
        self.security.audit_logger.record(
            "AGENT_COMPLETE", session_id, clean_query[:100], result.answer[:100],
            {"tools": result.tools_used, "confidence": result.confidence,
             "mode": result.mode, "time_ms": round(result.execution_time_ms)}
        )

        return {
            "answer": result.answer,
            "confidence": result.confidence,
            "tools_used": result.tools_used,
            "reasoning_steps": [
                {
                    "step": s.step_num,
                    "thought": s.thought,
                    "action": s.action,
                    "tool": s.tool_used,
                    "observation": s.observation,
                }
                for s in result.steps
            ],
            "execution_time_ms": round(result.execution_time_ms),
            "mode": result.mode,
            "threat_detected": False,
            "audit_hash": sec["audit_hash"],
        }

    def get_status(self) -> dict:
        react_status = self.react.get_status()
        sec_stats = self.security.get_stats()
        return {
            "status": "operational",
            "agent": {
                "mode": react_status["mode"],
                "llm_backend": react_status["llm_backend"],
                "version": react_status["version"],
            },
            "tools": {
                "fema_agent": {
                    "codes_indexed": len(self.fema.code_order),
                    "method": "TF-IDF + keyword matching",
                },
                "risk_agent": {
                    "rules": 8,
                    "method": "Named rule-based scoring",
                },
                "qa_agent": {
                    "knowledge_chunks": len(self.qa.chunk_ids),
                    "llm_enabled": self.qa._groq_client is not None,
                },
            },
            "security": sec_stats,
            "memory": {
                "active_sessions": self.memory.active_sessions,
            },
        }
