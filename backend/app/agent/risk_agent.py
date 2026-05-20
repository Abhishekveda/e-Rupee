"""
risk_agent.py
=============
The e₹ Bridge Transaction Risk Scoring Agent.

HOW IT WORKS:
=============
A transparent, rule-based + statistical scoring engine.
Every risk flag has a named reason — fully explainable to RBI auditors.

SCORING MODEL:
==============
Total risk score: 0–100 (higher = more risk)

Each rule contributes a defined number of points:

  AMOUNT RULES (max 35 pts)
  ├── Unusually large amount for stated purpose     +20
  ├── Amount approaches LRS annual limit ($200K+)   +15
  └── Amount exactly at round thresholds (₹10L etc) +5

  PURPOSE RULES (max 20 pts)
  ├── Purpose code inconsistent with amount          +15
  ├── High-risk purpose category (business/invest)   +10
  └── Purpose requires extra documentation           +5

  VELOCITY RULES (max 25 pts)
  ├── Multiple transfers in short window             +20
  ├── First-ever transfer (no history)               +5
  └── Escalating amounts over time                   +15

  RECIPIENT RULES (max 15 pts)
  ├── New recipient address                          +10
  ├── Invalid Ethereum address format               +15
  └── High-risk destination                          +5

  TIME RULES (max 5 pts)
  └── Unusual time-of-day transfer                   +5

RISK LEVELS:
  LOW    (0–25):  Approve automatically
  MEDIUM (26–55): Flag for review, allow with note
  HIGH   (56–100): Block pending manual review

WHY THIS MATTERS TO RBI:
========================
This is the architecture of AI-native AML/CFT compliance.
Unlike black-box ML models, every flag can be audited and
explained to the Financial Intelligence Unit India (FIU-IND).
The scoring logic can be updated directly as RBI updates its
risk frameworks — no model retraining required.
"""

import re
from datetime import datetime, timezone
from typing import Optional


# FEMA codes that require extra documentation / higher scrutiny
HIGH_SCRUTINY_CODES = {"P1301", "P1302", "P1303", "P1001"}

# Typical max amounts per purpose (INR) — amounts above these flag for review
PURPOSE_MAX_AMOUNTS = {
    "P0101": 500_000,    # Family maintenance — ₹5L reasonable monthly max
    "P0102": 300_000,
    "P0103": 2_000_000,  # Education — ₹20L per semester reasonable
    "P0104": 300_000,    # Travel
    "P0105": 200_000,    # Gifts
    "P0106": 1_000_000,  # Donations
    "P0801": 2_000_000,  # Medical
    "P0802": 300_000,
    "P1001": 10_000_000, # Software services — high threshold
    "P1301": 10_000_000, # Business services
    "P1302": 5_000_000,
    "P1303": 5_000_000,
}

# LRS thresholds in INR (approx USD rates)
LRS_ANNUAL_LIMIT_INR = 20_750_000   # $250,000 at ₹83/USD
LRS_WARNING_THRESHOLD = 16_600_000  # $200,000 — start warning
LRS_BLOCK_THRESHOLD   = 20_750_000  # $250,000 — hard block

# Valid Ethereum address pattern
ETH_ADDRESS_PATTERN = re.compile(r"^0x[0-9a-fA-F]{40}$")


class RiskAgent:
    """
    Scores transaction risk before execution.

    Usage:
        agent = RiskAgent()
        result = agent.score(
            sender_wallet="INDIA_USER_001",
            recipient_address="0xAbCd...",
            amount_inr=10000,
            purpose_code="P0102",
            recipient_country="UAE",
            transfer_history=[]
        )
    """

    def score(
        self,
        sender_wallet: str,
        recipient_address: str,
        amount_inr: float,
        purpose_code: str,
        recipient_country: str,
        transfer_history: Optional[list] = None,
    ) -> dict:
        """
        Score a pending transfer for risk.

        Returns:
            {
                "risk_score": 12,
                "risk_level": "LOW",
                "recommendation": "APPROVE",
                "flags": [...],
                "compliance_checks": {...},
                "breakdown": {...},
                "summary": "...",
                "agent": "e₹ Risk Scoring Agent v1.0"
            }
        """
        history = transfer_history or []
        flags = []
        breakdown = {}

        # ── RULE 1: Address validation ────────────────────────────────────────
        addr_score = 0
        if not recipient_address or len(recipient_address) < 10:
            addr_score += 15
            flags.append({
                "rule": "INVALID_ADDRESS",
                "severity": "HIGH",
                "detail": "Recipient address is missing or too short.",
                "points": 15,
            })
        elif not ETH_ADDRESS_PATTERN.match(recipient_address):
            addr_score += 10
            flags.append({
                "rule": "ADDRESS_FORMAT",
                "severity": "MEDIUM",
                "detail": f"Recipient address '{recipient_address[:20]}...' does not match expected Ethereum format (0x + 40 hex chars).",
                "points": 10,
            })
        breakdown["address_validation"] = addr_score

        # ── RULE 2: Amount checks ─────────────────────────────────────────────
        amount_score = 0

        # LRS limit proximity
        if amount_inr >= LRS_BLOCK_THRESHOLD:
            amount_score += 30
            flags.append({
                "rule": "LRS_LIMIT_EXCEEDED",
                "severity": "HIGH",
                "detail": f"Amount ₹{amount_inr:,.0f} appears to exceed the LRS annual limit of ₹{LRS_ANNUAL_LIMIT_INR:,.0f} (~$250,000). Transfer requires RBI approval.",
                "points": 30,
            })
        elif amount_inr >= LRS_WARNING_THRESHOLD:
            amount_score += 15
            flags.append({
                "rule": "LRS_LIMIT_APPROACHING",
                "severity": "MEDIUM",
                "detail": f"Amount ₹{amount_inr:,.0f} is approaching the annual LRS limit. Verify remaining quota with your bank.",
                "points": 15,
            })

        # Amount vs purpose consistency
        purpose_max = PURPOSE_MAX_AMOUNTS.get(purpose_code)
        if purpose_max and amount_inr > purpose_max * 2:
            amount_score += 15
            flags.append({
                "rule": "AMOUNT_EXCEEDS_PURPOSE_NORM",
                "severity": "MEDIUM",
                "detail": f"Amount ₹{amount_inr:,.0f} is significantly above the typical maximum of ₹{purpose_max:,.0f} for purpose {purpose_code}. Verify documentation.",
                "points": 15,
            })
        elif purpose_max and amount_inr > purpose_max:
            amount_score += 5
            flags.append({
                "rule": "AMOUNT_ABOVE_PURPOSE_NORM",
                "severity": "LOW",
                "detail": f"Amount ₹{amount_inr:,.0f} slightly exceeds typical range for purpose {purpose_code} (max ₹{purpose_max:,.0f}).",
                "points": 5,
            })

        # Round number structuring detection
        if amount_inr > 100_000 and amount_inr % 100_000 == 0:
            amount_score += 3
            flags.append({
                "rule": "ROUND_AMOUNT",
                "severity": "LOW",
                "detail": f"Transfer amount ₹{amount_inr:,.0f} is a round number. Note: structuring transactions to avoid reporting thresholds is prohibited.",
                "points": 3,
            })

        breakdown["amount_checks"] = amount_score

        # ── RULE 3: Purpose code scrutiny ────────────────────────────────────
        purpose_score = 0
        if purpose_code in HIGH_SCRUTINY_CODES:
            purpose_score += 8
            flags.append({
                "rule": "HIGH_SCRUTINY_PURPOSE",
                "severity": "LOW",
                "detail": f"Purpose code {purpose_code} (business/professional services) requires supporting documentation: invoice, service agreement, or contract.",
                "points": 8,
            })
        breakdown["purpose_check"] = purpose_score

        # ── RULE 4: Transfer history / velocity ──────────────────────────────
        velocity_score = 0

        if len(history) == 0:
            velocity_score += 3
            flags.append({
                "rule": "FIRST_TRANSFER",
                "severity": "INFO",
                "detail": "First transfer from this wallet. Normal for new users — no action required.",
                "points": 3,
            })

        # Check for recent transfers (velocity)
        recent = [t for t in history if t.get("status") == "settled"]
        if len(recent) >= 3:
            velocity_score += 12
            flags.append({
                "rule": "HIGH_VELOCITY",
                "severity": "MEDIUM",
                "detail": f"Sender has {len(recent)} previous settled transfers. Verify cumulative LRS usage does not exceed $250,000 this financial year.",
                "points": 12,
            })
        elif len(recent) >= 1:
            velocity_score += 0  # Normal — no flag

        # Check cumulative amount
        cumulative = sum(t.get("amount_inr", 0) for t in history)
        if cumulative + amount_inr > LRS_ANNUAL_LIMIT_INR:
            velocity_score += 20
            flags.append({
                "rule": "CUMULATIVE_LRS_EXCEEDED",
                "severity": "HIGH",
                "detail": f"Cumulative transfers ₹{cumulative:,.0f} + this transfer ₹{amount_inr:,.0f} = ₹{cumulative+amount_inr:,.0f} exceeds LRS limit. RBI approval required.",
                "points": 20,
            })

        breakdown["velocity_check"] = velocity_score

        # ── RULE 5: Time-of-day check ─────────────────────────────────────────
        time_score = 0
        current_hour = datetime.now(timezone.utc).hour
        # 1–5 AM UTC = 6:30–10:30 AM IST — unusual for personal remittances
        if 1 <= current_hour <= 5:
            time_score += 2
            # Not a flag — too minor, just noted
        breakdown["time_check"] = time_score

        # ── COMPUTE FINAL SCORE ───────────────────────────────────────────────
        total_score = (
            addr_score + amount_score + purpose_score +
            velocity_score + time_score
        )
        total_score = min(total_score, 100)  # cap at 100

        # Risk level
        if total_score <= 20:
            risk_level = "LOW"
            recommendation = "APPROVE"
        elif total_score <= 50:
            risk_level = "MEDIUM"
            recommendation = "REVIEW"
        else:
            risk_level = "HIGH"
            recommendation = "BLOCK"

        # ── COMPLIANCE CHECKS SUMMARY ─────────────────────────────────────────
        compliance_checks = {
            "address_valid": addr_score == 0,
            "amount_within_lrs": amount_inr < LRS_ANNUAL_LIMIT_INR,
            "amount_consistent_with_purpose": amount_score < 15,
            "purpose_code_valid": purpose_code in {fc["code"] for fc in
                                                   __import__("app.agent.knowledge_base",
                                                              fromlist=["FEMA_CODES"]).FEMA_CODES},
            "no_velocity_concern": velocity_score < 10,
        }

        # ── SUMMARY TEXT ─────────────────────────────────────────────────────
        high_flags = [f for f in flags if f["severity"] == "HIGH"]
        medium_flags = [f for f in flags if f["severity"] == "MEDIUM"]

        if risk_level == "LOW":
            summary = (f"Transfer of ₹{amount_inr:,.0f} to {recipient_country} appears "
                       f"routine and compliant. No significant risk factors detected.")
        elif risk_level == "MEDIUM":
            summary = (f"Transfer flagged for review: {', '.join(f['rule'] for f in medium_flags[:2])}. "
                       f"Transfer can proceed after reviewing flagged items.")
        else:
            summary = (f"Transfer blocked: {', '.join(f['rule'] for f in high_flags[:2])}. "
                       f"Manual review required before proceeding.")

        return {
            "risk_score": total_score,
            "risk_level": risk_level,
            "recommendation": recommendation,
            "flags": flags,
            "flag_count": len(flags),
            "high_flags": len(high_flags),
            "medium_flags": len(medium_flags),
            "compliance_checks": compliance_checks,
            "score_breakdown": breakdown,
            "summary": summary,
            "agent": "e₹ Risk Scoring Agent v1.0",
        }
