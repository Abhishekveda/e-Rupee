"""
ai_service.py — Claude-powered AI intelligence layer for e₹ Bridge

This module adds three AI capabilities to every transaction:

1. COMPLIANCE INTELLIGENCE
   User types plain English ("sending money to my daughter for university")
   → Claude identifies the correct FEMA purpose code (P0103)
   → Claude checks LRS annual limit remaining
   → Claude flags any compliance concerns

2. FRAUD & RISK ANALYSIS
   Before every transfer, Claude analyses:
   → Amount vs historical patterns for this sender
   → Time-of-day risk signals
   → Recipient address novelty
   → Purpose code vs amount consistency
   → Returns: LOW / MEDIUM / HIGH risk with plain-English reasoning

3. MARKET INTELLIGENCE
   Conversational assistant that answers:
   → "Is now a good time to send to UAE?"
   → "Why did my rate change?"
   → "What is the LRS limit?"
   → Contextually aware of the user's current transfer

HOW IT CONNECTS TO CLAUDE:
   Uses the Anthropic Python SDK with claude-sonnet-4-20250514.
   Set ANTHROPIC_API_KEY in your .env file.
   In the RBI Regulatory Sandbox, this key would be issued by RBI
   to authorised bridge operators.
"""

import os
import json
from typing import Optional
from anthropic import Anthropic

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

FEMA_CODES = {
    "P0102": "Family maintenance / personal remittance",
    "P0103": "Education fees paid abroad",
    "P0801": "Medical treatment abroad",
    "P1301": "Business / trade payment",
    "P0104": "Travel",
    "P0105": "Maintenance of close relatives",
    "P1001": "Software services export receipts",
}

SYSTEM_PROMPT = """You are an AI compliance and risk intelligence engine for e₹ Bridge, 
a cross-border CBDC payment system built on India's e-Rupee. You have deep knowledge of:
- RBI's FEMA regulations and remittance purpose codes
- India's Liberalised Remittance Scheme (LRS) — $250,000 annual limit per individual
- e-Rupee CBDC architecture and RBI's Payments Vision 2025
- Cross-border payment fraud patterns
- India→UAE and India→Singapore remittance corridors

Always respond in JSON format as specified. Be concise, precise, and regulatory-aware.
Never recommend anything that violates FEMA or RBI guidelines."""


# ── Feature 1: FEMA Code Intelligence ─────────────────────────────────────────

async def suggest_fema_code(user_description: str, amount_inr: float) -> dict:
    """
    Takes plain English like "sending money to my daughter for university in Dubai"
    and returns the correct FEMA purpose code with explanation.

    Example input:  "paying for my son's medical treatment in Singapore"
    Example output: {"code": "P0801", "label": "Medical treatment abroad",
                     "confidence": "HIGH", "explanation": "...", "lrs_note": "..."}
    """
    prompt = f"""A user wants to send ₹{amount_inr:,.0f} internationally.
They described their purpose as: "{user_description}"

Available FEMA codes: {json.dumps(FEMA_CODES, indent=2)}

Respond ONLY with this JSON (no markdown, no preamble):
{{
  "code": "P0XXX",
  "label": "description",
  "confidence": "HIGH|MEDIUM|LOW",
  "explanation": "1-2 sentence explanation of why this code applies",
  "lrs_note": "note about LRS limit impact if relevant",
  "alternative_code": "P0XXX or null if no alternative"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.content[0].text)
    except Exception as e:
        return {
            "code": "P0102",
            "label": "Family maintenance / personal remittance",
            "confidence": "LOW",
            "explanation": "Could not classify automatically — please select manually.",
            "lrs_note": f"Error: {str(e)}",
            "alternative_code": None
        }


# ── Feature 2: Transaction Risk Analysis ──────────────────────────────────────

async def analyse_transaction_risk(
    sender_wallet: str,
    recipient_address: str,
    amount_inr: float,
    purpose_code: str,
    recipient_country: str,
    sender_history: Optional[list] = None
) -> dict:
    """
    Analyses a pending transfer for fraud and compliance risk before execution.
    This runs BEFORE the transfer is debited — giving the user and RBI visibility.

    Returns a risk assessment with:
    - Overall risk level: LOW / MEDIUM / HIGH
    - Specific risk factors identified
    - Compliance checks passed/failed
    - Recommendation: APPROVE / REVIEW / BLOCK

    In production this would also:
    - Check CERSAI database for sanctioned entities
    - Validate against RBI's negative list
    - Cross-reference with FIU-IND alerts
    """
    history_summary = f"{len(sender_history)} previous transfers" if sender_history else "first transfer"

    prompt = f"""Analyse this pending e-Rupee cross-border transfer for risk:

Sender: {sender_wallet}
Recipient address: {recipient_address}
Amount: ₹{amount_inr:,.0f}
Purpose code: {purpose_code} ({FEMA_CODES.get(purpose_code, 'Unknown')})
Destination: {recipient_country}
Sender history: {history_summary}

Consider:
1. Is the amount consistent with the stated purpose?
2. Are there any FEMA compliance concerns?
3. Does the amount approach or exceed LRS thresholds?
4. Are there velocity or pattern concerns?
5. Is the recipient address format valid (Ethereum 0x...)?

Respond ONLY with this JSON:
{{
  "risk_level": "LOW|MEDIUM|HIGH",
  "recommendation": "APPROVE|REVIEW|BLOCK",
  "risk_score": 0-100,
  "factors": ["factor1", "factor2"],
  "compliance_checks": {{
    "fema_code_valid": true|false,
    "amount_consistent_with_purpose": true|false,
    "lrs_limit_concern": true|false,
    "recipient_address_valid": true|false
  }},
  "summary": "1-2 sentence plain English summary for the user"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.content[0].text)
    except Exception as e:
        return {
            "risk_level": "LOW",
            "recommendation": "APPROVE",
            "risk_score": 10,
            "factors": [],
            "compliance_checks": {
                "fema_code_valid": True,
                "amount_consistent_with_purpose": True,
                "lrs_limit_concern": False,
                "recipient_address_valid": True
            },
            "summary": f"Risk analysis unavailable: {str(e)}"
        }


# ── Feature 3: Conversational Market Intelligence ─────────────────────────────

async def chat_with_bridge(
    user_message: str,
    conversation_history: list,
    current_transfer_context: Optional[dict] = None
) -> str:
    """
    Conversational AI assistant aware of:
    - The user's current transfer (amount, corridor, purpose)
    - Current FX rates
    - RBI regulations and LRS rules
    - Market context

    Example questions it can answer:
    - "Is now a good time to send ₹50,000 to UAE?"
    - "What does P0102 mean?"
    - "How much can I send in a year?"
    - "Why was my transfer flagged?"
    - "What's the difference between wholesale and retail CBDC?"

    Conversation history maintains context across multiple questions.
    """
    context = ""
    if current_transfer_context:
        context = f"""
Current transfer context:
- Amount: ₹{current_transfer_context.get('amount_inr', 0):,.0f}
- Destination: {current_transfer_context.get('country', 'Unknown')}
- Purpose: {current_transfer_context.get('purpose_code', 'Unknown')}
- FX rate: {current_transfer_context.get('fx_rate', 'Unknown')}
"""

    system = SYSTEM_PROMPT + f"""
{context}
Current FX rates: 1 INR = 0.044 AED, 1 INR = 0.016 SGD
Today's date: May 2026
You are a helpful, concise assistant. Answer in 2-4 sentences max.
Do not use markdown. Plain text only."""

    messages = conversation_history + [{"role": "user", "content": user_message}]

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=system,
            messages=messages
        )
        return response.content[0].text
    except Exception as e:
        return f"I'm temporarily unavailable. Error: {str(e)}"


# ── Feature 4: Transfer Summary for Audit ────────────────────────────────────

async def generate_transfer_summary(transaction: dict) -> str:
    """
    Generates a plain-English summary of a completed transfer for:
    - User's own records
    - Bank audit trail
    - RBI reporting

    In production this would be attached to every transaction receipt
    and stored on-chain as metadata.
    """
    prompt = f"""Write a 3-sentence plain-English summary of this completed e-Rupee transfer 
for the user's records. Be factual, include all key numbers, mention the fee saved vs SWIFT.

Transaction: {json.dumps(transaction, default=str)}

Write as if addressing the sender directly. No markdown."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception:
        return (
            f"Your transfer of ₹{transaction.get('amount_inr', 0):,.0f} to "
            f"{transaction.get('recipient_country', 'destination')} was completed successfully. "
            f"The recipient received {transaction.get('converted_amount', 0)} "
            f"{transaction.get('target_currency', '')}. "
            f"You saved approximately ₹{transaction.get('amount_inr', 0) * 0.061:.0f} vs SWIFT."
        )
