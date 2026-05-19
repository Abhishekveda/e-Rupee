"""
e-Rupee CBDC Cross-Border Payment Bridge — Mock API
Simulates RBI's CBDC wholesale/retail endpoints as described in the
e-Rupee pilot documentation. Replace with live RBI API credentials
when the developer sandbox opens.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import uuid4
import asyncio
import httpx
import hashlib
import json
import time

app = FastAPI(
    title="e-Rupee CBDC Bridge API",
    description="Mock cross-border payment rail using simulated CBDC + Ethereum bridge",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory ledger (replace with PostgreSQL in prod) ─────────────────────────
wallets: dict[str, dict] = {
    "INDIA_USER_001": {"balance": 50000.00, "currency": "INR", "cbdc_type": "retail"},
    "INDIA_USER_002": {"balance": 120000.00, "currency": "INR", "cbdc_type": "retail"},
    "BANK_NOSTRO_SBI": {"balance": 5000000.00, "currency": "INR", "cbdc_type": "wholesale"},
}
transactions: dict[str, dict] = {}

# ── FX rates (in prod: pull from RBI reference rate or Chainlink oracle) ───────
FX_RATES = {
    "INR_AED": 0.044,   # 1 INR = 0.044 AED
    "INR_SGD": 0.016,   # 1 INR = 0.016 SGD
    "INR_USD": 0.012,   # 1 INR = 0.012 USD
    "INR_GBP": 0.0095,
}


# ── Schemas ────────────────────────────────────────────────────────────────────
class TransferRequest(BaseModel):
    sender_wallet: str = Field(..., example="INDIA_USER_001")
    recipient_address: str = Field(..., example="0xRecipientEthAddress")
    recipient_country: str = Field(..., example="UAE")
    amount_inr: float = Field(..., gt=0, example=10000.0)
    purpose_code: str = Field(..., example="P0102")  # RBI FEMA purpose code
    notes: Optional[str] = None

class WalletTopup(BaseModel):
    wallet_id: str
    amount: float

class FXQuoteRequest(BaseModel):
    amount_inr: float
    target_currency: str  # AED, SGD, USD, GBP


# ── Helper: simulate CBDC transaction hash ────────────────────────────────────
def make_cbdc_tx_hash(data: str) -> str:
    payload = f"{data}{time.time_ns()}"
    return "0xcbdc" + hashlib.sha256(payload.encode()).hexdigest()[:60]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "e-Rupee CBDC Bridge",
        "status": "operational",
        "note": "This is a PoC simulation. Live RBI API keys needed for production.",
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
    fee_inr = round(req.amount_inr * 0.002, 2)  # 0.2% bridge fee
    return {
        "quote_id": str(uuid4()),
        "from": "INR",
        "to": req.target_currency.upper(),
        "amount_inr": req.amount_inr,
        "fx_rate": rate,
        "converted_amount": converted,
        "bridge_fee_inr": fee_inr,
        "net_amount_inr": req.amount_inr - fee_inr,
        "valid_until": datetime.utcnow().isoformat() + "Z",
    }


@app.post("/v1/erupee/transfer")
async def initiate_transfer(req: TransferRequest, background_tasks: BackgroundTasks):
    """
    Core transfer endpoint. Flow:
    1. Validate sender CBDC wallet balance
    2. Debit e-Rupee from sender (CBDC lock)
    3. Compute FX conversion
    4. Relay locked amount to Ethereum bridge contract
    5. Return CBDC tx hash + bridge tx hash
    """
    # 1. Validate wallet
    if req.sender_wallet not in wallets:
        raise HTTPException(404, "Sender wallet not found")
    wallet = wallets[req.sender_wallet]

    # 2. Check balance (include 0.2% bridge fee)
    total_debit = req.amount_inr * 1.002
    if wallet["balance"] < total_debit:
        raise HTTPException(400, f"Insufficient balance. Need ₹{total_debit:.2f}, have ₹{wallet['balance']:.2f}")

    # 3. CBDC debit (atomic lock)
    cbdc_tx_hash = make_cbdc_tx_hash(f"{req.sender_wallet}{req.amount_inr}")
    wallet["balance"] = round(wallet["balance"] - total_debit, 2)

    # 4. FX conversion
    target_currency = "AED" if req.recipient_country == "UAE" else "SGD"
    rate_key = f"INR_{target_currency}"
    fx_rate = FX_RATES.get(rate_key, 0.016)
    converted_amount = round(req.amount_inr * fx_rate, 4)

    # 5. Simulate Ethereum bridge relay
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

    # Simulate async settlement after 3s
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


# ── Background: simulate bridge settlement ────────────────────────────────────
async def settle_transaction(tx_id: str):
    await asyncio.sleep(3)  # simulate blockchain finality
    if tx_id in transactions:
        transactions[tx_id]["status"] = "settled"
        transactions[tx_id]["settled_at"] = datetime.utcnow().isoformat() + "Z"
        transactions[tx_id]["settlement_block"] = 19_450_000 + hash(tx_id) % 1000
