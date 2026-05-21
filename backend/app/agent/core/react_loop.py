"""
react_loop.py
-------------
The core agentic reasoning engine for e₹ Bridge.

Implements the ReAct pattern (Reasoning + Acting) from:
"ReAct: Synergizing Reasoning and Acting in Language Models"
Yao et al., 2023 (Princeton / Google Brain)

HOW THE AGENT WORKS:
====================
Rather than routing a user query directly to a single function,
the agent reasons about what it needs to do, selects and calls
tools, observes the results, and iterates until it has a
complete answer. This produces more accurate and comprehensive
responses, particularly for complex multi-step queries.

Example:
  User: "My daughter is doing her MBA in Dubai. I want to send
         ₹5 lakh per semester. Is this okay and what should I know?"

  Agent reasoning trace:
    Thought 1: This query involves education remittance. I need
               to identify the FEMA code, check LRS compliance,
               and provide documentation requirements.
    Action 1:  classify_fema("MBA fees Dubai", 500000)
    Obs 1:     P0103, HIGH confidence
    Thought 2: Amount is ₹5L per semester, ~₹10L/year. Within LRS
               limit of ~₹2Cr but I should flag documentation.
    Action 2:  score_risk("...", 500000, "P0103", "UAE")
    Obs 2:     LOW risk, score 8. One note: requires fee demand notice.
    Thought 3: I now have everything. Compile a complete answer.
    Final:     Structured response with code, LRS note, docs needed.

The agent can run up to MAX_STEPS iterations before producing
a final answer. Each step is logged for audit purposes.

WITHOUT AN LLM:
===============
When no LLM backend is configured, the agent runs in
deterministic mode — the planner uses heuristic rules to
select tools, and the response is assembled from tool outputs
without natural language generation. This is fully auditable
and appropriate for production regulatory use.

WITH AN LLM:
============
When Groq, Ollama, Sarvam, or any other backend is configured,
the agent uses the LLM for reasoning steps while still calling
the deterministic tools for factual operations. The LLM
enhances the presentation of results; the facts themselves
come from the tools.
"""

import re
import time
from typing import Optional

from app.agent.core.llm_interface import get_llm
from app.agent.knowledge_base import FEMA_CODE_LOOKUP
from app.agent.fema_agent import FEMAAgent
from app.agent.risk_agent import RiskAgent
from app.agent.qa_agent import QAAgent

MAX_STEPS = 4
AGENT_VERSION = "e₹ Agentic AI v2.0"


class AgentStep:
    """Represents one step in the agent's reasoning trace."""
    def __init__(self, step_num: int, thought: str, action: str,
                 tool_used: str, observation: str):
        self.step_num = step_num
        self.thought = thought
        self.action = action
        self.tool_used = tool_used
        self.observation = observation
        self.timestamp = time.time()


class AgentResult:
    """The final output of an agent run."""
    def __init__(self):
        self.answer: str = ""
        self.steps: list[AgentStep] = []
        self.tools_used: list[str] = []
        self.confidence: str = "MEDIUM"
        self.sources: list[dict] = []
        self.execution_time_ms: float = 0
        self.mode: str = "deterministic"  # or "llm_augmented"


class ReactLoop:
    """
    The ReAct agent loop.

    Coordinates the planner, tools, and LLM to handle complex
    multi-step queries about FEMA compliance, risk assessment,
    and regulatory guidance.
    """

    def __init__(self):
        self.llm = get_llm()
        self.fema_agent = FEMAAgent()
        self.risk_agent = RiskAgent()
        self.qa_agent = QAAgent()
        self.mode = "llm_augmented" if self.llm.name != "logic" else "deterministic"

    def run(
        self,
        query: str,
        context: Optional[dict] = None,
        session_id: str = "default",
    ) -> AgentResult:
        """
        Execute the agent loop for a given query.

        Args:
            query:      The user's natural language question or request
            context:    Optional dict with transfer context (amount, purpose, etc.)
            session_id: For per-session state tracking

        Returns:
            AgentResult with answer, reasoning trace, and metadata
        """
        start = time.time()
        result = AgentResult()
        result.mode = self.mode
        ctx = context or {}

        # Step 1: Classify the intent of the query
        intent = self._classify_intent(query, ctx)

        # Step 2: Plan which tools to call
        plan = self._plan(intent, query, ctx)

        # Step 3: Execute tools according to the plan
        tool_outputs = {}
        for i, tool_call in enumerate(plan):
            step_start = time.time()
            thought = tool_call.get("thought", "")
            tool_name = tool_call["tool"]
            tool_args = tool_call.get("args", {})

            output = self._call_tool(tool_name, tool_args, query, ctx)
            tool_outputs[tool_name] = output
            result.tools_used.append(tool_name)

            step = AgentStep(
                step_num=i + 1,
                thought=thought,
                action=f"{tool_name}({', '.join(f'{k}={v}' for k, v in list(tool_args.items())[:2])})",
                tool_used=tool_name,
                observation=str(output)[:200],
            )
            result.steps.append(step)

        # Step 4: Synthesise the final answer
        result.answer = self._synthesise(query, intent, tool_outputs, ctx)
        result.confidence = self._assess_confidence(tool_outputs)
        result.execution_time_ms = (time.time() - start) * 1000

        return result

    # ── Intent classification ──────────────────────────────────────────────────

    def _classify_intent(self, query: str, ctx: dict) -> str:
        """
        Classifies the user's intent into one of:
          fema_only | risk_only | qa_only | fema_and_risk | full_check | market
        """
        q = query.lower()
        has_amount = bool(ctx.get("amount_inr") or re.search(r"₹[\d,]+|lakh|crore|\d+\s*rs", q))
        has_purpose = bool(ctx.get("purpose_description") or
                           any(w in q for w in ["university", "fees", "medical", "family",
                                                "business", "gift", "travel"]))
        has_risk_q = any(w in q for w in ["risk", "fraud", "safe", "suspicious",
                                           "flag", "block", "allow"])
        has_reg_q = any(w in q for w in ["what is", "how much", "lrs", "fema",
                                          "limit", "rule", "regulation", "allowed",
                                          "permitted", "code", "cbdc", "e-rupee"])
        has_market_q = any(w in q for w in ["rate", "fx", "exchange", "time to send",
                                              "when", "best time"])

        if has_amount and has_purpose and has_risk_q:
            return "full_check"
        if has_amount and has_purpose:
            return "fema_and_risk"
        if has_purpose and not has_amount:
            return "fema_only"
        if has_risk_q:
            return "risk_only"
        if has_market_q:
            return "market"
        return "qa_only"

    # ── Planner ────────────────────────────────────────────────────────────────

    def _plan(self, intent: str, query: str, ctx: dict) -> list[dict]:
        """
        Produces an ordered list of tool calls to execute.
        Each entry: {"tool": name, "args": {...}, "thought": reasoning}
        """
        amount = ctx.get("amount_inr", 0)
        purpose_desc = ctx.get("purpose_description", query)
        purpose_code = ctx.get("purpose_code", "P0102")
        sender = ctx.get("sender_wallet", "unknown")
        recipient = ctx.get("recipient_address", "0x0")
        country = ctx.get("recipient_country", "UAE")

        if intent == "full_check":
            return [
                {
                    "tool": "fema_classify",
                    "args": {"description": purpose_desc, "amount": amount},
                    "thought": "First identify the correct FEMA code for the stated purpose.",
                },
                {
                    "tool": "risk_score",
                    "args": {"sender": sender, "recipient": recipient,
                             "amount": amount, "purpose": purpose_code, "country": country},
                    "thought": "Then assess the risk profile of this transfer.",
                },
                {
                    "tool": "qa_retrieve",
                    "args": {"question": query},
                    "thought": "Finally retrieve any relevant regulatory context.",
                },
            ]
        elif intent == "fema_and_risk":
            return [
                {
                    "tool": "fema_classify",
                    "args": {"description": purpose_desc, "amount": amount},
                    "thought": "Classify the FEMA purpose code.",
                },
                {
                    "tool": "risk_score",
                    "args": {"sender": sender, "recipient": recipient,
                             "amount": amount, "purpose": purpose_code, "country": country},
                    "thought": "Score the risk for this transfer amount and purpose.",
                },
            ]
        elif intent == "fema_only":
            return [
                {
                    "tool": "fema_classify",
                    "args": {"description": purpose_desc, "amount": amount},
                    "thought": "Classify the FEMA purpose code from the description.",
                },
            ]
        elif intent == "risk_only":
            return [
                {
                    "tool": "risk_score",
                    "args": {"sender": sender, "recipient": recipient,
                             "amount": amount, "purpose": purpose_code, "country": country},
                    "thought": "Evaluate the risk profile of this transfer.",
                },
            ]
        else:  # qa_only or market
            return [
                {
                    "tool": "qa_retrieve",
                    "args": {"question": query},
                    "thought": "Retrieve relevant regulatory information for this question.",
                },
            ]

    # ── Tool execution ────────────────────────────────────────────────────────

    def _call_tool(self, tool_name: str, args: dict, query: str, ctx: dict) -> dict:
        try:
            if tool_name == "fema_classify":
                return self.fema_agent.classify(
                    args.get("description", query),
                    args.get("amount", 0),
                )
            elif tool_name == "risk_score":
                history = ctx.get("transfer_history", [])
                return self.risk_agent.score(
                    sender_wallet=args.get("sender", "unknown"),
                    recipient_address=args.get("recipient", "0x0"),
                    amount_inr=args.get("amount", 0),
                    purpose_code=args.get("purpose", "P0102"),
                    recipient_country=args.get("country", "UAE"),
                    transfer_history=history,
                )
            elif tool_name == "qa_retrieve":
                return self.qa_agent.answer(args.get("question", query))
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"error": str(e)}

    # ── Answer synthesis ──────────────────────────────────────────────────────

    def _synthesise(
        self, query: str, intent: str, tool_outputs: dict, ctx: dict
    ) -> str:
        """
        Produces the final answer from tool outputs.
        If an LLM is available, it formats the response naturally.
        Otherwise, assembles a structured plain-text answer.
        """
        if self.llm.name != "logic":
            return self._llm_synthesise(query, intent, tool_outputs, ctx)
        return self._rule_synthesise(intent, tool_outputs, ctx)

    def _rule_synthesise(self, intent: str, outputs: dict, ctx: dict) -> str:
        parts = []

        fema = outputs.get("fema_classify")
        risk = outputs.get("risk_score")
        qa = outputs.get("qa_retrieve")

        if fema and not fema.get("error"):
            parts.append(
                f"FEMA Code: {fema['code']} — {fema['label']} "
                f"({fema['confidence']} confidence). {fema['explanation']} "
                f"{fema['lrs_note']}"
            )
            if fema.get("lrs_warning"):
                parts.append(f"LRS Warning: {fema['lrs_warning']}")

        if risk and not risk.get("error"):
            parts.append(
                f"Risk Assessment: {risk['risk_level']} "
                f"(score {risk['risk_score']}/100). "
                f"Recommendation: {risk['recommendation']}. "
                f"{risk['summary']}"
            )
            for flag in risk.get("flags", []):
                if flag["severity"] in ("HIGH", "MEDIUM"):
                    parts.append(f"  → {flag['rule']}: {flag['detail']}")

        if qa and not qa.get("error"):
            parts.append(f"Regulatory context: {qa['answer']}")

        if not parts:
            return "I was unable to find relevant information. Please rephrase your question or contact RBI directly at fintech@rbi.org.in."

        return "\n\n".join(parts)

    def _llm_synthesise(self, query: str, intent: str, outputs: dict, ctx: dict) -> str:
        """Uses the configured LLM to generate a natural language answer."""
        summary = self._rule_synthesise(intent, outputs, ctx)
        system = (
            "You are the e₹ Bridge AI agent — a regulatory compliance assistant "
            "for cross-border CBDC payments. You are precise, cite regulatory sources, "
            "and answer in 3–5 sentences. Do not speculate beyond the provided facts."
        )
        prompt = (
            f"User question: {query}\n\n"
            f"Facts from compliance tools:\n{summary}\n\n"
            "Write a clear, helpful answer based only on the facts above."
        )
        llm_answer = self.llm.complete(system, prompt, max_tokens=350)
        return llm_answer if llm_answer else summary

    def _assess_confidence(self, outputs: dict) -> str:
        fema = outputs.get("fema_classify", {})
        if fema.get("confidence") == "HIGH":
            return "HIGH"
        if fema.get("confidence") == "LOW":
            return "LOW"
        return "MEDIUM"

    def get_status(self) -> dict:
        return {
            "mode": self.mode,
            "llm_backend": self.llm.name,
            "max_steps": MAX_STEPS,
            "version": AGENT_VERSION,
        }
