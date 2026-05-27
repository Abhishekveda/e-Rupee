"""
e-Rupee CBDC Cross-Border Payment Bridge API v2.0
==================================================
Combines the CBDC payment simulation layer with the
custom e₹ AI Agent (no external AI API required).

AI AGENT ENDPOINTS:
  POST /v1/agent/classify-purpose   — FEMA code from plain English
  POST /v1/agent/score-risk         — risk score before transfer
  POST /v1/agent/ask                — regulatory Q&A
  POST /v1/agent/pre-check          — combined FEMA + risk check
  GET  /v1/agent/status             — agent health check
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import uuid4
import asyncio
import hashlib
import time
import os

from app.agent.orchestrator import AgentOrchestrator

app = FastAPI(
    title="e₹ Bridge API",
    description="e-Rupee CBDC cross-border payment bridge with custom AI agent",
    version="2.0.0",
    docs_url="/api-docs",      # move swagger to /api-docs
    redoc_url="/api-redoc",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Serve the frontend at localhost:8000 ─────────────────────────────────────
_static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the live demo frontend at localhost:8000"""
    index = os.path.join(os.path.dirname(__file__), "..", "static", "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "e₹ Bridge API running. Place index.html in backend/static/"}

# Initialise AI agent once at startup
agent = AgentOrchestrator()

# In-memory store
wallets = {
    "INDIA_USER_001": {"balance": 50000.00, "currency": "INR", "cbdc_type": "retail"},
    "INDIA_USER_002": {"balance": 120000.00, "currency": "INR", "cbdc_type": "retail"},
}
transactions = {}
FX_RATES = {"INR_AED": 0.044, "INR_SGD": 0.016, "INR_USD": 0.012}


# ── Schemas ───────────────────────────────────────────────────────────────────

class TransferRequest(BaseModel):
    sender_wallet: str
    recipient_address: str
    recipient_country: str
    amount_inr: float = Field(..., gt=0)
    purpose_code: str
    notes: Optional[str] = None

class WalletTopup(BaseModel):
    wallet_id: str
    amount: float

class FXQuoteRequest(BaseModel):
    amount_inr: float
    target_currency: str

class AgentClassifyRequest(BaseModel):
    description: str = Field(..., example="paying my daughter's university fees in Dubai")
    amount_inr: float = Field(default=10000, example=500000)

class AgentRiskRequest(BaseModel):
    sender_wallet: str
    recipient_address: str
    amount_inr: float
    purpose_code: str
    recipient_country: str

class AgentAskRequest(BaseModel):
    question: str = Field(..., example="What is the LRS annual limit?")
    session_id: str = Field(default="default")

class AgentPreCheckRequest(BaseModel):
    description: str = ""
    sender_wallet: str
    recipient_address: str
    amount_inr: float
    purpose_code: str
    recipient_country: str


# ── Core endpoints ────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "e₹ Bridge API v2.0",
        "ai_agent": "Custom e₹ AI Agent (no external API needed)",
        "features": ["cbdc_simulation", "fema_classification", "risk_scoring", "regulatory_qa"],
    }

@app.get("/v1/wallets/{wallet_id}")
def get_wallet(wallet_id: str):
    if wallet_id not in wallets:
        raise HTTPException(404, "Wallet not found")
    return {"wallet_id": wallet_id, **wallets[wallet_id]}

@app.post("/v1/wallets/topup")
def topup(req: WalletTopup):
    if req.wallet_id not in wallets:
        wallets[req.wallet_id] = {"balance": 0, "currency": "INR", "cbdc_type": "retail"}
    wallets[req.wallet_id]["balance"] += req.amount
    return {"wallet_id": req.wallet_id, "new_balance": wallets[req.wallet_id]["balance"]}

@app.post("/v1/fx/quote")
def fx_quote(req: FXQuoteRequest):
    key = f"INR_{req.target_currency.upper()}"
    if key not in FX_RATES:
        raise HTTPException(400, f"Unsupported pair: {key}")
    rate = FX_RATES[key]
    fee = round(req.amount_inr * 0.002, 2)
    return {
        "from": "INR", "to": req.target_currency.upper(),
        "amount_inr": req.amount_inr, "fx_rate": rate,
        "converted_amount": round(req.amount_inr * rate, 4),
        "bridge_fee_inr": fee,
        "swift_equivalent_fee": round(req.amount_inr * 0.063, 2),
        "savings_vs_swift": round(req.amount_inr * 0.061, 2),
    }

@app.post("/v1/erupee/transfer")
async def transfer(req: TransferRequest, bg: BackgroundTasks):
    if req.sender_wallet not in wallets:
        raise HTTPException(404, "Wallet not found")
    wallet = wallets[req.sender_wallet]
    total = req.amount_inr * 1.002
    if wallet["balance"] < total:
        raise HTTPException(400, f"Insufficient balance. Need ₹{total:.2f}")

    cbdc_hash = "0xcbdc" + hashlib.sha256(f"{req.sender_wallet}{req.amount_inr}{time.time_ns()}".encode()).hexdigest()[:60]
    wallet["balance"] = round(wallet["balance"] - total, 2)
    target_currency = "AED" if req.recipient_country == "UAE" else "SGD"
    fx_rate = FX_RATES.get(f"INR_{target_currency}", 0.016)
    bridge_hash = "0xbridge" + hashlib.sha256(cbdc_hash.encode()).hexdigest()[:56]
    tx_id = str(uuid4())

    record = {
        "tx_id": tx_id, "status": "pending_bridge",
        "sender_wallet": req.sender_wallet,
        "recipient_address": req.recipient_address,
        "recipient_country": req.recipient_country,
        "amount_inr": req.amount_inr,
        "bridge_fee_inr": round(req.amount_inr * 0.002, 2),
        "fx_rate": fx_rate,
        "converted_amount": round(req.amount_inr * fx_rate, 4),
        "target_currency": target_currency,
        "purpose_code": req.purpose_code,
        "cbdc_tx_hash": cbdc_hash,
        "bridge_tx_hash": bridge_hash,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    transactions[tx_id] = record
    bg.add_task(_settle, tx_id)
    return record

@app.get("/v1/transactions/{tx_id}")
def get_tx(tx_id: str):
    if tx_id not in transactions:
        raise HTTPException(404, "Not found")
    return transactions[tx_id]

@app.get("/v1/transactions")
def list_tx(wallet_id: Optional[str] = None):
    txns = list(transactions.values())
    if wallet_id:
        txns = [t for t in txns if t["sender_wallet"] == wallet_id]
    return {"count": len(txns), "transactions": txns}

async def _settle(tx_id: str):
    await asyncio.sleep(3)
    if tx_id in transactions:
        transactions[tx_id]["status"] = "settled"
        transactions[tx_id]["settled_at"] = datetime.utcnow().isoformat() + "Z"
        transactions[tx_id]["settlement_block"] = 19_450_000 + hash(tx_id) % 1000


# ── AI Agent endpoints ────────────────────────────────────────────────────────

@app.get("/v1/agent/status")
def agent_status():
    """Check which AI agents are active and their capabilities."""
    return agent.get_status()

@app.post("/v1/agent/classify-purpose")
def classify_purpose(req: AgentClassifyRequest):
    """
    FEMA Code Classification Agent.
    Input: plain English description of remittance purpose.
    Output: FEMA code, confidence, explanation — no external API needed.
    """
    result = agent.classify_purpose(req.description, req.amount_inr)
    return result

@app.post("/v1/agent/score-risk")
def score_risk(req: AgentRiskRequest):
    """
    Transaction Risk Scoring Agent.
    Scores 0-100. Every flag has a named rule and explanation.
    """
    history = [t for t in transactions.values() if t["sender_wallet"] == req.sender_wallet]
    result = agent.score_risk(
        sender_wallet=req.sender_wallet,
        recipient_address=req.recipient_address,
        amount_inr=req.amount_inr,
        purpose_code=req.purpose_code,
        recipient_country=req.recipient_country,
        transfer_history=history,
    )
    return result

@app.post("/v1/agent/ask")
def ask_agent(req: AgentAskRequest):
    """
    Regulatory Q&A Agent.
    RAG over RBI circulars, FEMA codes, LRS rules.
    No external LLM needed (optional Groq key enhances responses).
    """
    result = agent.answer_question(req.question, req.session_id)
    return result

@app.post("/v1/agent/pre-check")
def pre_check(req: AgentPreCheckRequest):
    """
    Combined pre-flight check: FEMA classification + risk scoring.
    Run this before executing a transfer.
    """
    history = [t for t in transactions.values() if t["sender_wallet"] == req.sender_wallet]
    result = agent.pre_transfer_check(
        description=req.description,
        sender_wallet=req.sender_wallet,
        recipient_address=req.recipient_address,
        amount_inr=req.amount_inr,
        purpose_code=req.purpose_code,
        recipient_country=req.recipient_country,
        transfer_history=history,
    )
    return result


# ── Agentic endpoint (full ReAct loop) ────────────────────────────────────────

class AgentRunRequest(BaseModel):
    query: str = Field(..., example="My daughter is doing MBA in Dubai, I want to send ₹5L per semester. What FEMA code and is it within LRS?")
    session_id: str = Field(default="default")
    context: Optional[dict] = None


@app.post("/v1/agent/run")
def run_agent(req: AgentRunRequest):
    """
    Full agentic reasoning endpoint.

    Unlike the direct tool endpoints, this runs the complete
    ReAct loop: the agent plans which tools to use, calls them,
    observes the results, and synthesises a comprehensive answer.

    Use this for complex, multi-faceted queries.
    Use /v1/agent/classify-purpose or /v1/agent/score-risk
    for single-purpose lookups.
    """
    result = agent.run_agent(
        query=req.query,
        context=req.context,
        session_id=req.session_id,
    )
    return result


@app.get("/v1/security/audit-log")
def get_audit_log(n: int = 20):
    """Returns the last N entries from the immutable audit log."""
    return {
        "entries": agent.security.get_audit_log(n),
        "chain_intact": agent.security.audit_logger.verify_chain(),
        "total_events": agent.security.audit_logger.total_events,
    }


# ── INR Bridge Currency endpoints ─────────────────────────────────────────────
# USD → INR (e-Rupee) → AED/SGD
# Makes INR the settlement currency for third-country payments
# Aligned to RBI's SRVA (Special Rupee Vostro Account) framework

class BridgeTransferRequest(BaseModel):
    """
    Multi-hop transfer: foreign sender → INR settlement → foreign recipient.
    The e-Rupee is the bridge currency — neither party needs to hold INR.
    This is the architecture for INR internationalisation.

    Example: Canadian sender (CAD) → Indian e-Rupee bridge → UAE recipient (AED)
    """
    sender_country: str = Field(..., example="CA")
    sender_currency: str = Field(..., example="CAD")
    sender_amount: float = Field(..., gt=0, example=200.0)
    recipient_country: str = Field(..., example="UAE")
    recipient_currency: str = Field(..., example="AED")
    recipient_address: str = Field(..., example="0xRecipientAddress")
    purpose_code: str = Field(..., example="P0102")

# Multi-currency FX rates (all via INR)
MULTI_FX = {
    "CAD_INR": 62.0,
    "USD_INR": 83.0,
    "GBP_INR": 105.0,
    "EUR_INR": 91.0,
    "INR_AED": 0.044,
    "INR_SGD": 0.016,
    "INR_USD": 0.012,
    "INR_GBP": 0.0095,
}

@app.post("/v1/bridge/multi-hop-quote")
def multi_hop_quote(req: BridgeTransferRequest):
    """
    Quote for a multi-hop transfer where INR is the bridge currency.

    Flow: Sender currency → INR → Recipient currency
    This is how the rupee becomes a global settlement currency.
    The sender and recipient never hold INR — it is used only for settlement.
    Aligned to RBI Special Rupee Vostro Account (SRVA) framework.
    """
    src_key = f"{req.sender_currency.upper()}_INR"
    dst_key = f"INR_{req.recipient_currency.upper()}"

    if src_key not in MULTI_FX:
        raise HTTPException(400, f"Source currency {req.sender_currency} not supported")
    if dst_key not in MULTI_FX:
        raise HTTPException(400, f"Destination currency {req.recipient_currency} not supported")

    # Convert source → INR
    inr_amount = req.sender_amount * MULTI_FX[src_key]
    # Convert INR → destination
    dst_amount = round(inr_amount * MULTI_FX[dst_key], 4)

    bridge_fee_pct = 0.002  # 0.2%
    bridge_fee_inr = round(inr_amount * bridge_fee_pct, 2)
    swift_fee_inr = round(inr_amount * 0.063, 2)

    return {
        "quote_type": "inr_bridge",
        "sender": {
            "country": req.sender_country,
            "currency": req.sender_currency,
            "amount": req.sender_amount,
        },
        "bridge": {
            "currency": "INR",
            "amount_inr": round(inr_amount, 2),
            "e_rupee_used": True,
            "srva_framework": True,
        },
        "recipient": {
            "country": req.recipient_country,
            "currency": req.recipient_currency,
            "amount": dst_amount,
        },
        "fees": {
            "bridge_fee_inr": bridge_fee_inr,
            "bridge_fee_pct": "0.2%",
            "swift_equivalent_fee_inr": swift_fee_inr,
            "savings_inr": round(swift_fee_inr - bridge_fee_inr, 2),
            "savings_pct": "96.8%",
        },
        "fx_path": f"{req.sender_currency} → INR (e-Rupee) → {req.recipient_currency}",
        "dollar_used": False,
        "note": "INR used as bridge currency — no USD required. Aligned to RBI SRVA framework.",
    }

@app.post("/v1/bridge/multi-hop-transfer")
async def multi_hop_transfer(req: BridgeTransferRequest, bg: BackgroundTasks):
    """
    Execute a multi-hop transfer through the INR bridge.
    Makes the INR the settlement currency for international payments.
    """
    src_key = f"{req.sender_currency.upper()}_INR"
    dst_key = f"INR_{req.recipient_currency.upper()}"

    if src_key not in MULTI_FX or dst_key not in MULTI_FX:
        raise HTTPException(400, "Unsupported currency pair")

    inr_amount = req.sender_amount * MULTI_FX[src_key]
    dst_amount = round(inr_amount * MULTI_FX[dst_key], 4)
    bridge_fee_inr = round(inr_amount * 0.002, 2)

    # Enforce PA-CB transaction limit (₹25 lakh)
    if inr_amount > 2_500_000:
        raise HTTPException(400, f"Transaction exceeds PA-CB limit of ₹25,00,000 (RBI PA Directions 2025)")

    cbdc_hash = "0xcbdc" + hashlib.sha256(
        f"bridge{req.sender_amount}{req.sender_currency}{time.time_ns()}".encode()
    ).hexdigest()[:60]

    tx_id = str(uuid4())
    record = {
        "tx_id": tx_id,
        "type": "inr_bridge",
        "status": "pending",
        "sender_country": req.sender_country,
        "sender_currency": req.sender_currency,
        "sender_amount": req.sender_amount,
        "inr_bridge_amount": round(inr_amount, 2),
        "bridge_fee_inr": bridge_fee_inr,
        "recipient_country": req.recipient_country,
        "recipient_currency": req.recipient_currency,
        "recipient_amount": dst_amount,
        "recipient_address": req.recipient_address,
        "purpose_code": req.purpose_code,
        "cbdc_tx_hash": cbdc_hash,
        "fx_path": f"{req.sender_currency} → INR → {req.recipient_currency}",
        "dollar_used": False,
        "srva_settlement": True,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "pa_cb_compliant": True,
        "data_stored_india": True,
    }
    transactions[tx_id] = record
    bg.add_task(_settle_bridge, tx_id)
    return record

async def _settle_bridge(tx_id: str):
    await asyncio.sleep(3)
    if tx_id in transactions:
        transactions[tx_id]["status"] = "settled"
        transactions[tx_id]["settled_at"] = datetime.utcnow().isoformat() + "Z"
        transactions[tx_id]["settlement_block"] = 19_450_000 + hash(tx_id) % 1000
        transactions[tx_id]["note"] = "INR bridge settlement complete. Dollar bypassed."
