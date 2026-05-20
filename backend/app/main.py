"""
e-Rupee CBDC Cross-Border Payment Bridge — API
================================================

This is the core backend for e₹ Bridge. It does two things:

LAYER 1: CBDC SIMULATION
  Simulates the RBI e-Rupee retail wallet API (e₹-R pilot).
  When RBI opens a developer sandbox, replace the mock functions
  with real API calls to fintech.rbi.org.in

LAYER 2: AI INTELLIGENCE
  Uses Claude (Anthropic) to add three AI capabilities:
  - FEMA code suggestion from plain English
  - Transaction risk analysis before execution
  - Conversational market intelligence assistant

ENDPOINTS:
  GET  /                           — health check
  GET  /v1/wallets/{id}            — get wallet balance
  POST /v1/wallets/topup           — add test funds
  POST /v1/fx/quote                — get FX rate quote
  POST /v1/erupee/transfer         — execute transfer (main flow)
  GET  /v1/transactions/{id}       — get transaction status
  GET  /v1/transactions            — list all transactions

  AI ENDPOINTS:
  POST /v1/ai/suggest-purpose      — FEMA code from plain English
  POST /v1/ai/risk-analysis        — risk score before transfer
  POST /v1/ai/chat                 — conversational assistant
  POST /v1/ai/transfer-summary     — plain-English transfer summary

ENVIRONMENT VARIABLES:
  ANTHROPIC_API_KEY  — required for AI endpoints
  (all others optional for local development)
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import uuid4
import asyncio
import hashlib
import time

from app.ai_service import (
    suggest_fema_code,
    analyse_transaction_risk,
    chat_with_bridge,
    generate_transfer_summary,
)

app = FastAPI(
    title="e₹ Bridge API",
    description="e-Rupee CBDC cross-border payment bridge with AI intelligence layer",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory store (replace with PostgreSQL in production) ───────────────────
wallets: dict = {
    "INDIA_USER_001": {"balance": 50000.00, "currency": "INR", "cbdc_type": "retail"},
    "INDIA_USER_002": {"balance": 120000.00, "currency": "INR", "cbdc_type": "retail"},
    "BANK_NOSTRO_SBI": {"balance": 5000000.00, "currency": "INR", "cbdc_type": "wholesale"},
}
transactions: dict = {}
conversation_histories: dict = {}  # session_id → list of messages

# ── FX rates (replace with Chainlink oracle in production) ────────────────────
FX_RATES = {"INR_AED": 0.044, "INR_SGD": 0.016, "INR_USD": 0.012, "INR_GBP": 0.0095}


# ── Schemas ───────────────────────────────────────────────────────────────────

class TransferRequest(BaseModel):
    sender_wallet: str = Field(..., example="INDIA_USER_001")
    recipient_address: str = Field(..., example="0xRecipientEthAddress")
    recipient_country: str = Field(..., example="UAE")
    amount_inr: float = Field(..., gt=0, example=10000.0)
    purpose_code: str = Field(..., example="P0102")
    notes: Optional[str] = None

class WalletTopup(BaseModel):
    wallet_id: str
    amount: float

class FXQuoteRequest(BaseModel):
    amount_inr: float
    target_currency: str

class AISuggestPurposeRequest(BaseModel):
    """
    AI Feature 1: User describes their purpose in plain English.
    Claude identifies the correct FEMA code.

    Example: "I'm paying for my daughter's MBA fees in Dubai"
    → {"code": "P0103", "label": "Education fees paid abroad", ...}
    """
    description: str = Field(..., example="paying for my daughter's university fees in Dubai")
    amount_inr: float = Field(..., example=500000.0)

class AIRiskRequest(BaseModel):
    """
    AI Feature 2: Risk analysis before a transfer is executed.
    Claude scores the transaction and flags any concerns.
    """
    sender_wallet: str
    recipient_address: str
    amount_inr: float
    purpose_code: str
    recipient_country: str

class AIChatRequest(BaseModel):
    """
    AI Feature 3: Conversational assistant.
    Maintains conversation history per session.

    Example questions:
    - "What is the LRS annual limit?"
    - "Is ₹50,000 too much to send for family maintenance?"
    - "What's the difference between P0102 and P0105?"
    """
    session_id: str = Field(..., example="user-abc-123")
    message: str = Field(..., example="Is now a good time to send money to UAE?")
    transfer_context: Optional[dict] = None  # optional: current transfer details

class AITransferSummaryRequest(BaseModel):
    """
    AI Feature 4: Plain-English summary of a completed transfer.
    Useful for the user's own records and RBI audit trail.
    """
    transaction_id: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_cbdc_hash(data: str) -> str:
    payload = f"{data}{time.time_ns()}"
    return "0xcbdc" + hashlib.sha256(payload.encode()).hexdigest()[:60]


# ── Core transfer endpoints ───────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "e₹ Bridge API v2.0",
        "features": ["cbdc_simulation", "fx_oracle", "ai_compliance", "ai_risk", "ai_chat"],
        "ai_powered": True,
        "note": "e-Rupee APIs are simulated. Connect to RBI developer sandbox for production.",
    }


@app.get("/v1/wallets/{wallet_id}")
def get_wallet(wallet_id: str):
    if wallet_id not in wallets:
        raise HTTPException(404, f"Wallet {wallet_id} not found")
    return {"wallet_id": wallet_id, **wallets[wallet_id]}


@app.post("/v1/wallets/topup")
def topup_wallet(req: WalletTopup):
    if req.wallet_id not in wallets:
        wallets[req.wallet_id] = {"balance": 0, "currency": "INR", "cbdc_type": "retail"}
    wallets[req.wallet_id]["balance"] += req.amount
    return {"wallet_id": req.wallet_id, "new_balance": wallets[req.wallet_id]["balance"]}


@app.post("/v1/fx/quote")
def get_fx_quote(req: FXQuoteRequest):
    key = f"INR_{req.target_currency.upper()}"
    if key not in FX_RATES:
        raise HTTPException(400, f"Currency pair {key} not supported")
    rate = FX_RATES[key]
    converted = round(req.amount_inr * rate, 4)
    fee_inr = round(req.amount_inr * 0.002, 2)
    swift_fee = round(req.amount_inr * 0.063, 2)
    return {
        "quote_id": str(uuid4()),
        "from": "INR",
        "to": req.target_currency.upper(),
        "amount_inr": req.amount_inr,
        "fx_rate": rate,
        "converted_amount": converted,
        "bridge_fee_inr": fee_inr,
        "swift_equivalent_fee": swift_fee,
        "savings_vs_swift": round(swift_fee - fee_inr, 2),
        "net_amount_inr": req.amount_inr - fee_inr,
        "valid_until": datetime.utcnow().isoformat() + "Z",
    }


@app.post("/v1/erupee/transfer")
async def initiate_transfer(req: TransferRequest, background_tasks: BackgroundTasks):
    """
    Main transfer flow:
    1. Validate wallet balance
    2. Debit e-Rupee (CBDC lock)
    3. Compute FX
    4. Relay to Ethereum bridge
    5. Return receipt with CBDC + bridge hashes
    """
    if req.sender_wallet not in wallets:
        raise HTTPException(404, "Sender wallet not found")
    wallet = wallets[req.sender_wallet]
    total_debit = req.amount_inr * 1.002
    if wallet["balance"] < total_debit:
        raise HTTPException(400, f"Insufficient balance. Need ₹{total_debit:.2f}, have ₹{wallet['balance']:.2f}")

    cbdc_tx_hash = make_cbdc_hash(f"{req.sender_wallet}{req.amount_inr}")
    wallet["balance"] = round(wallet["balance"] - total_debit, 2)

    target_currency = "AED" if req.recipient_country == "UAE" else "SGD"
    rate_key = f"INR_{target_currency}"
    fx_rate = FX_RATES.get(rate_key, 0.016)
    converted_amount = round(req.amount_inr * fx_rate, 4)
    bridge_hash = "0xbridge" + hashlib.sha256(cbdc_tx_hash.encode()).hexdigest()[:56]

    tx_id = str(uuid4())
    record = {
        "tx_id": tx_id,
        "status": "pending_bridge",
        "sender_wallet": req.sender_wallet,
        "recipient_address": req.recipient_address,
        "recipient_country": req.recipient_country,
        "amount_inr": req.amount_inr,
        "bridge_fee_inr": round(req.amount_inr * 0.002, 2),
        "fx_rate": fx_rate,
        "converted_amount": converted_amount,
        "target_currency": target_currency,
        "purpose_code": req.purpose_code,
        "cbdc_tx_hash": cbdc_tx_hash,
        "bridge_tx_hash": bridge_hash,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "estimated_settlement": "< 90 seconds",
    }
    transactions[tx_id] = record
    background_tasks.add_task(settle_transaction, tx_id)
    return record


@app.get("/v1/transactions/{tx_id}")
def get_transaction(tx_id: str):
    if tx_id not in transactions:
        raise HTTPException(404, "Transaction not found")
    return transactions[tx_id]


@app.get("/v1/transactions")
def list_transactions(wallet_id: Optional[str] = None):
    txns = list(transactions.values())
    if wallet_id:
        txns = [t for t in txns if t["sender_wallet"] == wallet_id]
    return {"count": len(txns), "transactions": txns}


async def settle_transaction(tx_id: str):
    await asyncio.sleep(3)
    if tx_id in transactions:
        transactions[tx_id]["status"] = "settled"
        transactions[tx_id]["settled_at"] = datetime.utcnow().isoformat() + "Z"
        transactions[tx_id]["settlement_block"] = 19_450_000 + hash(tx_id) % 1000


# ── AI endpoints ──────────────────────────────────────────────────────────────

@app.post("/v1/ai/suggest-purpose")
async def ai_suggest_purpose(req: AISuggestPurposeRequest):
    """
    AI Feature 1: FEMA Code Intelligence

    WHY THIS MATTERS:
    Most users don't know FEMA codes. They describe their purpose
    in plain English. Claude maps it to the correct regulatory code,
    reducing compliance errors significantly.

    This is the difference between a user accidentally selecting P0102
    (family maintenance) when they mean P0103 (education fees) —
    which can trigger RBI compliance reviews.
    """
    result = await suggest_fema_code(req.description, req.amount_inr)
    return {"ai_suggestion": result, "powered_by": "claude-sonnet-4-20250514"}


@app.post("/v1/ai/risk-analysis")
async def ai_risk_analysis(req: AIRiskRequest):
    """
    AI Feature 2: Transaction Risk Analysis

    WHY THIS MATTERS:
    This runs BEFORE the transfer executes — giving both the user
    and RBI a pre-flight compliance check. In production this would
    integrate with CERSAI (sanctioned entities) and FIU-IND (suspicious
    transaction reports).

    This is what makes e₹ Bridge different from a simple payment bridge —
    it has regulatory intelligence built in, not bolted on afterward.
    """
    sender_txns = [t for t in transactions.values() if t["sender_wallet"] == req.sender_wallet]
    result = await analyse_transaction_risk(
        sender_wallet=req.sender_wallet,
        recipient_address=req.recipient_address,
        amount_inr=req.amount_inr,
        purpose_code=req.purpose_code,
        recipient_country=req.recipient_country,
        sender_history=sender_txns,
    )
    return {"risk_analysis": result, "powered_by": "claude-sonnet-4-20250514"}


@app.post("/v1/ai/chat")
async def ai_chat(req: AIChatRequest):
    """
    AI Feature 3: Conversational Market Intelligence

    WHY THIS MATTERS:
    Users making cross-border transfers have questions:
    - "How much can I send this year?" (LRS limit tracking)
    - "What does this FEMA code mean?"
    - "Is this transfer compliant?"

    Instead of reading 40-page RBI circulars, they ask Claude.
    The assistant is contextually aware of their current transfer,
    their wallet history, and current FX rates.

    In production this could also connect to:
    - RBI's real-time FX reference rate feed
    - Live notification when LRS limit is approaching
    - Regulatory change alerts
    """
    if req.session_id not in conversation_histories:
        conversation_histories[req.session_id] = []

    history = conversation_histories[req.session_id]
    response_text = await chat_with_bridge(
        user_message=req.message,
        conversation_history=history,
        current_transfer_context=req.transfer_context,
    )

    # Maintain conversation history (keep last 10 exchanges = 20 messages)
    history.append({"role": "user", "content": req.message})
    history.append({"role": "assistant", "content": response_text})
    conversation_histories[req.session_id] = history[-20:]

    return {
        "response": response_text,
        "session_id": req.session_id,
        "powered_by": "claude-sonnet-4-20250514"
    }


@app.post("/v1/ai/transfer-summary")
async def ai_transfer_summary(req: AITransferSummaryRequest):
    """
    AI Feature 4: Transfer Summary

    Generates a plain-English audit summary for every completed transfer.
    This is attached to the transaction receipt and forms part of
    the RBI-required audit trail for cross-border CBDC transfers.
    """
    if req.transaction_id not in transactions:
        raise HTTPException(404, "Transaction not found")
    tx = transactions[req.transaction_id]
    summary = await generate_transfer_summary(tx)
    return {"summary": summary, "transaction_id": req.transaction_id}
