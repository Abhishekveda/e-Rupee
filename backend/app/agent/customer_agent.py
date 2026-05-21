"""
customer_agent.py
-----------------
Customer Service AI Agent for e₹ Bridge.

This agent handles inbound user queries with full awareness of:
  - The user's account status and KYC level
  - Their current wallet balance
  - Their recent transaction history
  - Their LRS usage for the current financial year
  - The current status of any pending transfer

It answers questions like:
  - "Where is my transfer?"
  - "Why was my transfer flagged?"
  - "How much can I still send this year?"
  - "What documents do I need to send more than $10,000?"
  - "My recipient hasn't received the money yet"

When context is available, responses are personalised. When not,
the agent falls back to general regulatory guidance from the knowledge base.

The agent does NOT have access to sensitive user PII — it only
receives the minimum data needed to answer the question.
"""

import re
from datetime import datetime, timezone
from typing import Optional
from app.agent.knowledge_base import RBI_KNOWLEDGE_CHUNKS, FEMA_CODE_LOOKUP

# Maximum LRS limit in INR (approximate, based on ₹83/USD)
LRS_LIMIT_INR = 20_750_000


class CustomerAgent:
    """Answers user queries with transaction and account context."""

    def answer(
        self,
        question: str,
        user_context: Optional[dict] = None,
        transaction_context: Optional[dict] = None,
    ) -> dict:
        """
        Answer a customer query.

        Args:
            question:            User's question in plain English
            user_context:        {'name', 'kyc_status', 'lrs_used_inr', 'balance'}
            transaction_context: Latest transaction dict if relevant
        """
        q = question.lower().strip()
        response = self._route(q, user_context, transaction_context)

        return {
            "answer": response["text"],
            "intent": response["intent"],
            "suggested_actions": response.get("actions", []),
            "escalate_to_human": response.get("escalate", False),
            "agent": "e₹ Customer Service Agent v1.0",
        }

    def _route(self, q: str, user: Optional[dict], tx: Optional[dict]) -> dict:
        """Route to the correct handler based on detected intent."""

        # Status queries
        if any(w in q for w in ["where", "status", "pending", "received", "arrived", "reach"]):
            return self._handle_status(q, tx)

        # LRS / limit queries
        if any(w in q for w in ["lrs", "limit", "how much", "maximum", "send more", "allowance", "annual"]):
            return self._handle_lrs(q, user)

        # Fee queries
        if any(w in q for w in ["fee", "charge", "cost", "expensive", "price", "rate"]):
            return self._handle_fees(q, tx)

        # Flagged / blocked queries
        if any(w in q for w in ["flagged", "blocked", "rejected", "declined", "failed", "why"]):
            return self._handle_flagged(q, tx)

        # FEMA / compliance
        if any(w in q for w in ["fema", "purpose", "code", "p01", "p13", "document", "compliance"]):
            return self._handle_fema(q)

        # KYC queries
        if any(w in q for w in ["kyc", "verify", "aadhaar", "pan", "identity", "verification"]):
            return self._handle_kyc(q, user)

        # Account / balance
        if any(w in q for w in ["balance", "account", "wallet", "how much do i have"]):
            return self._handle_balance(q, user)

        # General fallback
        return self._handle_general(q)

    def _handle_status(self, q: str, tx: Optional[dict]) -> dict:
        if not tx:
            return {
                "intent": "transfer_status",
                "text": "I don't have a specific transfer in context. Your recent transfers are listed in the Transactions tab. Each transfer shows its current status — Pending, Settled, or Flagged. Settlements typically complete within 3 seconds of initiation.",
                "actions": ["View transactions"],
            }
        status = tx.get("status", "unknown")
        amount = tx.get("amount_inr", 0)
        currency = tx.get("target_currency", "AED")
        converted = tx.get("converted_amount", 0)

        if status == "settled":
            settled_at = tx.get("settled_at", "")
            block = tx.get("settlement_block", "")
            return {
                "intent": "transfer_status",
                "text": f"Your transfer of ₹{amount:,.0f} has been settled successfully. The recipient received {converted} {currency}. Settlement was confirmed on block #{block}. The full receipt is available in your transaction history.",
                "actions": ["View receipt", "Download receipt"],
            }
        elif status == "pending":
            return {
                "intent": "transfer_status",
                "text": f"Your transfer of ₹{amount:,.0f} is currently processing. e₹ Bridge settlements complete in under 3 seconds. If this transfer has been pending for more than 60 seconds, please contact support.",
                "actions": ["Refresh status", "Contact support"],
            }
        elif status == "flagged":
            risk = tx.get("ai_risk_level", "MEDIUM")
            return {
                "intent": "transfer_status",
                "text": f"Your transfer has been flagged for review by the AI Risk Agent (risk level: {risk}). This does not mean it has been rejected. A compliance review typically takes 1–2 business hours. You may be asked to provide supporting documentation.",
                "actions": ["View risk report", "Upload documents", "Contact support"],
                "escalate": True,
            }
        return {
            "intent": "transfer_status",
            "text": f"Transfer status: {status}. Please check your transaction history for full details.",
            "actions": ["View transactions"],
        }

    def _handle_lrs(self, q: str, user: Optional[dict]) -> dict:
        if user:
            used = user.get("lrs_used_inr", 0)
            remaining = max(0, LRS_LIMIT_INR - used)
            pct_used = (used / LRS_LIMIT_INR) * 100
            text = (
                f"Your LRS status for this financial year: "
                f"₹{used:,.0f} used ({pct_used:.1f}%), "
                f"₹{remaining:,.0f} remaining. "
                f"The annual LRS limit is ₹{LRS_LIMIT_INR:,.0f} (approximately $250,000). "
                f"This limit resets on 1 April each year."
            )
            if remaining < 2_000_000:
                text += " You are approaching your annual limit — please consult an Authorised Dealer bank before your next large transfer."
        else:
            text = (
                "Under the Liberalised Remittance Scheme (LRS), Indian residents can remit up to "
                "$250,000 (approximately ₹2.07 crore) per financial year (April–March) for permitted "
                "purposes including education, medical treatment, family maintenance, and travel. "
                "Log in to your account to check your personal LRS usage."
            )
        return {
            "intent": "lrs_query",
            "text": text,
            "actions": ["View LRS usage", "LRS rules on RBI website"],
        }

    def _handle_fees(self, q: str, tx: Optional[dict]) -> dict:
        if tx:
            fee = tx.get("bridge_fee_inr", 0)
            amount = tx.get("amount_inr", 0)
            swift_equiv = amount * 0.063
            text = (
                f"For your transfer of ₹{amount:,.0f}: bridge fee was ₹{fee:,.0f} (0.2%). "
                f"A SWIFT wire for the same amount would have cost approximately ₹{swift_equiv:,.0f} (6.3%). "
                f"You saved ₹{swift_equiv - fee:,.0f} by using e₹ Bridge."
            )
        else:
            text = (
                "e₹ Bridge charges a flat 0.2% bridge fee on all transfers. "
                "There are no hidden charges, no flat per-transfer fees, and no exchange rate markup. "
                "For comparison: SWIFT charges approximately 6.3% on average (World Bank 2024). "
                "On a ₹10,000 transfer, the difference is ₹610."
            )
        return {"intent": "fee_query", "text": text, "actions": ["See comparison"]}

    def _handle_flagged(self, q: str, tx: Optional[dict]) -> dict:
        if tx and tx.get("ai_risk_level") in ["MEDIUM", "HIGH"]:
            score = tx.get("ai_risk_score", 0)
            level = tx.get("ai_risk_level", "MEDIUM")
            text = (
                f"Your transfer was flagged by the AI Risk Agent with a score of {score}/100 ({level} risk). "
                f"Common reasons include: amount larger than typical for the stated purpose, "
                f"approaching LRS annual limit, or a new recipient address. "
                f"To resolve this quickly, upload a supporting document matching your purpose code "
                f"(e.g., university admission letter for P0103, medical certificate for P0801)."
            )
            return {
                "intent": "flagged_query",
                "text": text,
                "actions": ["Upload documents", "View risk report", "Contact compliance team"],
                "escalate": True,
            }
        return {
            "intent": "flagged_query",
            "text": "Transfers may be flagged if they exceed typical amounts for the stated purpose, approach LRS limits, or if the recipient address is new. If you believe your transfer was incorrectly flagged, please contact our compliance team with supporting documentation.",
            "actions": ["Contact support"],
            "escalate": True,
        }

    def _handle_fema(self, q: str) -> dict:
        return {
            "intent": "fema_query",
            "text": (
                "FEMA purpose codes classify why you are sending money abroad. "
                "The AI agent automatically suggests the correct code when you describe your purpose. "
                "Common codes: P0102 (family maintenance), P0103 (education), P0801 (medical), "
                "P1301 (business services). Using the wrong code can delay your transfer. "
                "The AI suggestion feature is designed to prevent this."
            ),
            "actions": ["Use AI FEMA helper", "View all FEMA codes"],
        }

    def _handle_kyc(self, q: str, user: Optional[dict]) -> dict:
        if user:
            status = user.get("kyc_status", "pending")
            if status == "verified":
                return {"intent": "kyc_query",
                        "text": "Your KYC verification is complete. You have full access to all transfer limits.",
                        "actions": []}
            elif status == "pending":
                return {"intent": "kyc_query",
                        "text": "Your KYC is pending. To complete verification, please submit your Aadhaar number (last 4 digits) and PAN. Verification typically takes 24 hours.",
                        "actions": ["Complete KYC", "Upload documents"],
                        "escalate": False}
        return {
            "intent": "kyc_query",
            "text": "KYC verification is required for transfers above ₹50,000. You will need your Aadhaar number and PAN. The process takes under 5 minutes and verification is typically completed within 24 hours.",
            "actions": ["Start KYC", "What documents are needed?"],
        }

    def _handle_balance(self, q: str, user: Optional[dict]) -> dict:
        if user and user.get("balance") is not None:
            bal = user["balance"]
            return {
                "intent": "balance_query",
                "text": f"Your e-Rupee wallet balance is ₹{bal:,.2f}. To add funds, ask your bank to top up your e₹-R wallet via the participating bank list on rbi.org.in.",
                "actions": ["Top up wallet", "View transactions"],
            }
        return {
            "intent": "balance_query",
            "text": "Log in to view your e-Rupee wallet balance. Your balance is the amount available to transfer.",
            "actions": ["Log in"],
        }

    def _handle_general(self, q: str) -> dict:
        return {
            "intent": "general",
            "text": "I can help you with: transfer status, LRS limits, FEMA purpose codes, fees, KYC verification, and account balance. Could you describe what you need more specifically?",
            "actions": ["Track a transfer", "Check LRS limit", "Fee calculator"],
            "escalate": False,
        }
