"""
AI Compliance & Fraud Detection Module
e₹ Bridge — RBIH Showcase 2026

This module adds an AI intelligence layer on top of the CBDC bridge.
Every transfer passes through three AI checks before being executed:

1. FEMA Compliance AI     — checks purpose codes, LRS limits, flagged entities
2. Fraud Risk Scorer      — anomaly detection on transaction patterns
3. FX Timing Advisor      — recommends optimal send time based on rate patterns

In production: replace rule-based scoring with trained ML models
(Random Forest for fraud, LSTM for FX prediction, fine-tuned LLM for compliance).
For PoC: deterministic rules + Claude API for natural language compliance Q&A.
"""

from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
import os
import json
from datetime import datetime, time


# ── Schemas ────────────────────────────────────────────────────────────────────

class ComplianceCheckRequest(BaseModel):
    sender_wallet: str
    recipient_country: str
    amount_inr: float
    purpose_code: str
    sender_ytd_transfers: Optional[float] = 0.0   # year-to-date INR sent


class FraudScoreRequest(BaseModel):
    sender_wallet: str
    amount_inr: float
    recipient_country: str
    hour_of_day: Optional[int] = None             # 0–23
    transfers_last_24h: Optional[int] = 0


class FXAdviceRequest(BaseModel):
    amount_inr: float
    target_currency: str    # AED, SGD, USD
    urgency: str            # "immediate", "flexible", "planned"


class AIQueryRequest(BaseModel):
    question: str
    context: Optional[str] = None   # e.g. "user is sending ₹50,000 to UAE"


# ── FEMA Purpose Code Registry ─────────────────────────────────────────────────

FEMA_CODES = {
    "P0102": {
        "name": "Family maintenance / personal remittance",
        "max_single_inr": 2_500_000,
        "requires_docs_above_inr": 500_000,
        "allowed_countries": "all",
    },
    "P0103": {
        "name": "Education fees abroad",
        "max_single_inr": 5_000_000,
        "requires_docs_above_inr": 100_000,
        "allowed_countries": "all",
    },
    "P0801": {
        "name": "Medical treatment abroad",
        "max_single_inr": 25_000_000,
        "requires_docs_above_inr": 1_000_000,
        "allowed_countries": "all",
    },
    "P1301": {
        "name": "Business / trade payment",
        "max_single_inr": 10_000_000,
        "requires_docs_above_inr": 200_000,
        "allowed_countries": "all",
        "requires_gst": True,
    },
}

# LRS annual limit per sender: USD 250,000 ≈ INR 2,08,75,000
LRS_ANNUAL_LIMIT_INR = 20_875_000


# ── 1. FEMA Compliance AI ──────────────────────────────────────────────────────

def check_fema_compliance(req: ComplianceCheckRequest) -> dict:
    """
    Deterministic FEMA compliance check.
    Returns: {compliant: bool, risk_level: str, flags: list, advice: str}
    """
    flags = []
    advice_parts = []

    # Check purpose code exists
    if req.purpose_code not in FEMA_CODES:
        return {
            "compliant": False,
            "risk_level": "BLOCKED",
            "flags": [f"Unknown FEMA purpose code: {req.purpose_code}"],
            "advice": f"Use a valid code. Common ones: P0102 (family), P0103 (education), P1301 (business).",
        }

    code_info = FEMA_CODES[req.purpose_code]

    # LRS annual limit check
    projected_ytd = req.sender_ytd_transfers + req.amount_inr
    if projected_ytd > LRS_ANNUAL_LIMIT_INR:
        flags.append(
            f"Transfer would exceed LRS annual limit. "
            f"YTD: ₹{req.sender_ytd_transfers:,.0f} + ₹{req.amount_inr:,.0f} "
            f"> ₹{LRS_ANNUAL_LIMIT_INR:,.0f}"
        )

    # Single transfer limit
    if req.amount_inr > code_info["max_single_inr"]:
        flags.append(
            f"Amount ₹{req.amount_inr:,.0f} exceeds single-transfer limit "
            f"of ₹{code_info['max_single_inr']:,.0f} for {req.purpose_code}"
        )

    # Documentation threshold
    if req.amount_inr > code_info["requires_docs_above_inr"]:
        advice_parts.append(
            f"Transfers above ₹{code_info['requires_docs_above_inr']:,.0f} "
            f"for {req.purpose_code} require supporting documents."
        )

    # GST requirement for business
    if code_info.get("requires_gst"):
        advice_parts.append("P1301 transfers require GSTIN of the Indian remitter.")

    # Large transfer warning
    if req.amount_inr > 1_000_000:
        flags.append("Transfer > ₹10 Lakh: enhanced due diligence applies.")

    risk_level = "LOW"
    if len(flags) == 1 and "documentation" not in flags[0].lower():
        risk_level = "MEDIUM"
    if len(flags) >= 2:
        risk_level = "HIGH"
    if any("exceed" in f.lower() or "blocked" in f.lower() for f in flags):
        risk_level = "BLOCKED"

    compliant = risk_level not in ("HIGH", "BLOCKED") or len(flags) == 0

    return {
        "compliant": compliant,
        "risk_level": risk_level,
        "purpose_code": req.purpose_code,
        "purpose_name": code_info["name"],
        "flags": flags,
        "advice": " ".join(advice_parts) if advice_parts else "Transfer looks compliant.",
        "documents_required": req.amount_inr > code_info["requires_docs_above_inr"],
        "lrs_used_percent": round((projected_ytd / LRS_ANNUAL_LIMIT_INR) * 100, 1),
    }


# ── 2. Fraud Risk Scorer ───────────────────────────────────────────────────────

def score_fraud_risk(req: FraudScoreRequest) -> dict:
    """
    Rule-based fraud scoring (PoC).
    Production: replace with trained Random Forest on historical transaction data.
    Score 0–100: 0 = very low risk, 100 = blocked.
    """
    score = 0
    signals = []

    # Large amount signal
    if req.amount_inr > 500_000:
        score += 15
        signals.append("Large transfer amount")
    if req.amount_inr > 1_000_000:
        score += 20
        signals.append("Very large transfer — enhanced review")

    # Velocity check
    if req.transfers_last_24h >= 3:
        score += 25
        signals.append(f"High velocity: {req.transfers_last_24h} transfers in 24h")
    if req.transfers_last_24h >= 5:
        score += 20
        signals.append("Extremely high velocity — potential structuring")

    # Odd hours (11pm–5am IST)
    hour = req.hour_of_day or datetime.utcnow().hour
    ist_hour = (hour + 5) % 24  # approximate IST
    if 23 <= ist_hour or ist_hour <= 5:
        score += 10
        signals.append("Transfer initiated during unusual hours (IST)")

    # Round number structuring
    if req.amount_inr % 100_000 == 0 and req.amount_inr >= 500_000:
        score += 8
        signals.append("Round-number transfer pattern")

    risk_label = "LOW"
    if score >= 25:
        risk_label = "MEDIUM"
    if score >= 50:
        risk_label = "HIGH"
    if score >= 75:
        risk_label = "REVIEW"

    return {
        "fraud_score": min(score, 100),
        "risk_label": risk_label,
        "signals": signals,
        "recommended_action": (
            "PROCEED" if risk_label == "LOW" else
            "PROCEED_WITH_LOG" if risk_label == "MEDIUM" else
            "MANUAL_REVIEW" if risk_label == "HIGH" else
            "BLOCK_AND_ALERT"
        ),
        "explanation": (
            "No significant risk signals detected." if not signals
            else f"Detected {len(signals)} risk signal(s): {'; '.join(signals)}."
        ),
    }


# ── 3. FX Timing Advisor ───────────────────────────────────────────────────────

# Simulated intraday FX patterns (INR/AED)
# Production: replace with live Chainlink oracle + LSTM time-series model
INTRADAY_PATTERN = {
    "AED": {
        "best_hours_ist": [9, 10, 14, 15],   # morning open + afternoon session
        "worst_hours_ist": [22, 23, 0, 1],
        "weekly_best_day": "Tuesday",
        "avg_rate": 0.044,
        "rate_variance": 0.0008,
    },
    "SGD": {
        "best_hours_ist": [8, 9, 13, 14],
        "worst_hours_ist": [21, 22, 23],
        "weekly_best_day": "Wednesday",
        "avg_rate": 0.016,
        "rate_variance": 0.0003,
    },
}


def get_fx_advice(req: FXAdviceRequest) -> dict:
    """
    FX timing recommendation.
    Production: LSTM model trained on 5-year INR/AED & INR/SGD tick data.
    """
    curr = req.target_currency.upper()
    if curr not in INTRADAY_PATTERN:
        return {"advice": "Currency not supported for AI timing advice."}

    pattern = INTRADAY_PATTERN[curr]
    current_hour_ist = (datetime.utcnow().hour + 5) % 24

    is_good_time = current_hour_ist in pattern["best_hours_ist"]
    saving_potential = pattern["rate_variance"] * req.amount_inr

    advice = ""
    confidence = "MEDIUM"

    if req.urgency == "immediate":
        advice = "Sending now. For immediate transfers rate timing is secondary — bridge fee savings vs SWIFT already dominate."
        confidence = "N/A"
    elif is_good_time:
        advice = f"Good time to send. You're in an optimal window (IST {current_hour_ist}:00). Estimated rate: {pattern['avg_rate'] + pattern['rate_variance']:.4f} {curr}/INR."
        confidence = "HIGH"
    else:
        best_h = pattern["best_hours_ist"][0]
        advice = f"Consider waiting. Best rate windows are typically around {best_h}:00–{best_h+1}:00 IST and {pattern['weekly_best_day']}s. Potential extra saving: ₹{saving_potential:.0f}."
        confidence = "MEDIUM"

    return {
        "current_rate": pattern["avg_rate"],
        "optimal_rate_estimate": pattern["avg_rate"] + pattern["rate_variance"],
        "is_good_time_now": is_good_time,
        "best_hours_ist": pattern["best_hours_ist"],
        "best_day": pattern["weekly_best_day"],
        "potential_extra_saving_inr": round(saving_potential, 2),
        "advice": advice,
        "confidence": confidence,
        "urgency": req.urgency,
    }


# ── 4. Claude AI Q&A (natural language compliance assistant) ───────────────────

async def ask_ai_assistant(req: AIQueryRequest) -> dict:
    """
    Routes user questions to Claude via Anthropic API.
    Scoped strictly to CBDC, FEMA, remittance, and RBI policy topics.

    In production: add conversation history, user context, transaction state.
    API key loaded from environment variable ANTHROPIC_API_KEY.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {
            "answer": "AI assistant requires ANTHROPIC_API_KEY environment variable. Set it in your .env file.",
            "source": "config_error",
        }

    system_prompt = """You are an AI compliance assistant for the e₹ Bridge — a cross-border CBDC 
payment platform built on India's e-Rupee. You help users understand:
- FEMA regulations and purpose codes
- RBI CBDC pilot and e-Rupee architecture  
- LRS (Liberalised Remittance Scheme) rules
- Cross-border payment corridors (India→UAE, India→Singapore)
- How the e₹ Bridge works technically
- General remittance and compliance questions

Be concise, accurate, and cite RBI policy where relevant.
If asked anything outside fintech/CBDC/payments/compliance, politely redirect.
Never give legal advice — say "consult a CA or compliance officer for your specific case."
Always mention that bridge fee is 0.2% vs SWIFT's 6.3% when relevant."""

    context_msg = f"\nUser context: {req.context}" if req.context else ""

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 400,
                    "system": system_prompt,
                    "messages": [
                        {"role": "user", "content": req.question + context_msg}
                    ],
                },
            )
            data = response.json()
            answer = data["content"][0]["text"]
            return {"answer": answer, "source": "claude_ai", "model": "claude-haiku"}

    except Exception as e:
        return {
            "answer": f"AI assistant temporarily unavailable: {str(e)}",
            "source": "error",
        }
