"""
cbdc/engine.py
==============
The actual CBDC engine for e₹ Bridge.

This is what connects to the real RBI e-Rupee API when it becomes
available. Until then, the simulation layer runs in its place.

WHAT RBI NEEDS TO PROVIDE (Developer Sandbox):
  1. e₹-R Wallet API — debit/credit retail wallets
  2. CBDC Transaction API — create and track transactions
  3. FX Reference Rate API — official INR exchange rates
  4. KYC Verification API — confirm user is KYC-verified
  5. LRS Tracking API — current-year LRS usage per PAN

WHAT WE HAVE BUILT:
  - The full protocol layer above those APIs
  - The AI compliance layer
  - The smart contracts
  - The multi-sig security
  - The ZK commitment scheme

When RBI opens the sandbox, the swap is:
  CBDCEngineSimulated → CBDCEngineRBI
  Three lines of config, zero code changes.

BRICS INTEROPERABILITY:
  For each partner country CBDC:
  - UAE: CBUAE Digital Dirham API (sandbox available)
  - Singapore: MAS Project Orchid API
  - Russia: Bank of Russia CBDC (e-Ruble) API
  - Brazil: BCB DREX API
  - China: PBOC e-CNY API (requires bilateral agreement)

  Each destination CBDC has its own adapter.
  The core protocol is identical for all of them.
"""

import os
import hashlib
import secrets
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

log = logging.getLogger(__name__)


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class WalletBalance:
    wallet_id:   str
    balance_inr: float
    cbdc_type:   str        # "retail" or "wholesale"
    is_frozen:   bool
    kyc_status:  str        # "verified", "pending", "rejected"
    lrs_used_inr: float
    lrs_limit_inr: float = 20_750_000.0   # ~$250,000 at ₹83/USD


@dataclass
class CBDCTransaction:
    tx_id:          str
    wallet_id:      str
    amount_inr:     float
    direction:      str         # "debit" or "credit"
    cbdc_hash:      str         # On-chain transaction hash
    status:         str         # "pending", "confirmed", "failed"
    created_at:     datetime
    confirmed_at:   Optional[datetime] = None
    block_number:   Optional[int] = None
    compliance_hash: Optional[str] = None


@dataclass
class FXQuote:
    pair:           str         # e.g. "INR_AED"
    rate:           float       # 1 INR = rate destination currency
    source:         str         # "rbi_reference", "chainlink", "simulated"
    valid_until:    datetime
    spread_bps:     int = 5     # Spread in basis points
    mid_rate:       float = 0.0 # Mid-market rate before spread


@dataclass
class SettlementResult:
    success:            bool
    transfer_id:        str
    cbdc_tx_hash:       str
    bridge_tx_hash:     str
    amount_inr:         float
    destination_amount: float
    destination_currency: str
    fee_inr:            float
    settlement_time_ms: int
    block_number:       Optional[int]
    error:              Optional[str] = None


# ── Abstract interface ────────────────────────────────────────────────────────

class CBDCEngineBase(ABC):

    @abstractmethod
    def get_wallet(self, wallet_id: str) -> Optional[WalletBalance]:
        ...

    @abstractmethod
    def debit_wallet(self, wallet_id: str, amount_inr: float,
                     compliance_hash: str) -> CBDCTransaction:
        ...

    @abstractmethod
    def get_fx_quote(self, destination_currency: str, amount_inr: float) -> FXQuote:
        ...

    @abstractmethod
    def settle(self, transfer_id: str, sender_wallet: str, recipient_address: str,
               amount_inr: float, destination_currency: str,
               compliance_hash: str) -> SettlementResult:
        ...


# ── Simulation engine (PoC) ───────────────────────────────────────────────────

class CBDCEngineSimulated(CBDCEngineBase):
    """
    Full simulation of the RBI e-Rupee API.
    Mirrors exactly what the production CBDCEngineRBI will do.
    Replace this class to go live.
    """

    # FX rates — in production these come from RBI's daily reference rate
    FX_RATES = {
        "AED": 0.044,
        "SGD": 0.016,
        "USD": 0.012,
        "GBP": 0.0095,
        "EUR": 0.011,
        "RUB": 0.93,
        "BRL": 0.062,
        "ZAR": 0.22,
        "SAR": 0.045,
        "CNY": 0.086,   # e-CNY when bilateral agreement exists
        "IDR": 190.0,
        "MYR": 0.056,
    }

    def __init__(self):
        # Simulated wallet store — in production: RBI e-Rupee wallet API
        self._wallets: dict[str, WalletBalance] = {
            "INDIA_USER_001": WalletBalance(
                wallet_id="INDIA_USER_001",
                balance_inr=500_000.0,
                cbdc_type="retail",
                is_frozen=False,
                kyc_status="verified",
                lrs_used_inr=125_000.0,
            ),
            "INDIA_USER_002": WalletBalance(
                wallet_id="INDIA_USER_002",
                balance_inr=1_200_000.0,
                cbdc_type="retail",
                is_frozen=False,
                kyc_status="verified",
                lrs_used_inr=0.0,
            ),
            "BANK_SBI_NOSTRO": WalletBalance(
                wallet_id="BANK_SBI_NOSTRO",
                balance_inr=500_000_000.0,
                cbdc_type="wholesale",
                is_frozen=False,
                kyc_status="verified",
                lrs_used_inr=0.0,
            ),
        }
        self._transactions: list[CBDCTransaction] = []

    def get_wallet(self, wallet_id: str) -> Optional[WalletBalance]:
        return self._wallets.get(wallet_id)

    def create_wallet(self, wallet_id: str, initial_balance: float = 50_000.0) -> WalletBalance:
        if wallet_id not in self._wallets:
            self._wallets[wallet_id] = WalletBalance(
                wallet_id=wallet_id,
                balance_inr=initial_balance,
                cbdc_type="retail",
                is_frozen=False,
                kyc_status="pending",
                lrs_used_inr=0.0,
            )
        return self._wallets[wallet_id]

    def debit_wallet(self, wallet_id: str, amount_inr: float,
                     compliance_hash: str) -> CBDCTransaction:
        wallet = self._wallets.get(wallet_id)
        if not wallet:
            raise ValueError(f"Wallet {wallet_id} not found")
        if wallet.is_frozen:
            raise ValueError(f"Wallet {wallet_id} is frozen")
        if wallet.balance_inr < amount_inr:
            raise ValueError(
                f"Insufficient balance: have ₹{wallet.balance_inr:,.2f}, "
                f"need ₹{amount_inr:,.2f}"
            )
        if wallet.kyc_status != "verified":
            raise ValueError(f"Wallet {wallet_id} KYC not verified")

        # Simulate the CBDC debit
        wallet.balance_inr -= amount_inr
        wallet.lrs_used_inr += amount_inr

        cbdc_hash = self._generate_cbdc_hash(wallet_id, amount_inr)
        tx = CBDCTransaction(
            tx_id=str(uuid4()),
            wallet_id=wallet_id,
            amount_inr=amount_inr,
            direction="debit",
            cbdc_hash=cbdc_hash,
            status="confirmed",
            created_at=datetime.now(timezone.utc),
            confirmed_at=datetime.now(timezone.utc),
            block_number=self._simulate_block_number(),
            compliance_hash=compliance_hash,
        )
        self._transactions.append(tx)
        return tx

    def get_fx_quote(self, destination_currency: str, amount_inr: float) -> FXQuote:
        currency = destination_currency.upper()
        if currency not in self.FX_RATES:
            raise ValueError(f"Unsupported currency: {currency}")

        rate = self.FX_RATES[currency]
        # Apply a minimal spread (0.05%) to simulate real FX market
        spread_bps = 5
        buy_rate = rate * (1 - spread_bps / 10000)

        from datetime import timedelta
        return FXQuote(
            pair=f"INR_{currency}",
            rate=buy_rate,
            source="simulated",
            valid_until=datetime.now(timezone.utc) + timedelta(minutes=15),
            spread_bps=spread_bps,
            mid_rate=rate,
        )

    def settle(
        self,
        transfer_id: str,
        sender_wallet: str,
        recipient_address: str,
        amount_inr: float,
        destination_currency: str,
        compliance_hash: str,
    ) -> SettlementResult:
        import time
        start = time.time()

        bridge_fee_pct = 0.002   # 0.2%
        fee_inr = round(amount_inr * bridge_fee_pct, 2)
        net_inr = amount_inr - fee_inr

        # Get FX quote
        quote = self.get_fx_quote(destination_currency, net_inr)
        dest_amount = round(net_inr * quote.rate, 4)

        # Debit the wallet
        cbdc_tx = self.debit_wallet(sender_wallet, amount_inr, compliance_hash)

        # Generate bridge hash (in production: Ethereum transaction hash)
        bridge_hash = self._generate_bridge_hash(cbdc_tx.cbdc_hash, recipient_address)

        elapsed_ms = int((time.time() - start) * 1000)

        return SettlementResult(
            success=True,
            transfer_id=transfer_id,
            cbdc_tx_hash=cbdc_tx.cbdc_hash,
            bridge_tx_hash=bridge_hash,
            amount_inr=amount_inr,
            destination_amount=dest_amount,
            destination_currency=destination_currency,
            fee_inr=fee_inr,
            settlement_time_ms=elapsed_ms,
            block_number=cbdc_tx.block_number,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _generate_cbdc_hash(wallet_id: str, amount: float) -> str:
        raw = f"cbdc:{wallet_id}:{amount}:{secrets.token_hex(16)}"
        return "0xcbdc" + hashlib.sha256(raw.encode()).hexdigest()[:60]

    @staticmethod
    def _generate_bridge_hash(cbdc_hash: str, recipient: str) -> str:
        raw = f"bridge:{cbdc_hash}:{recipient}:{secrets.token_hex(16)}"
        return "0xbridge" + hashlib.sha256(raw.encode()).hexdigest()[:56]

    @staticmethod
    def _simulate_block_number() -> int:
        import random
        return 19_450_000 + random.randint(0, 10_000)


# ── Production engine stub ────────────────────────────────────────────────────
# Uncomment and implement when RBI Developer Sandbox opens

class CBDCEngineRBI(CBDCEngineBase):
    """
    Production e-Rupee API integration.
    Replace CBDCEngineSimulated with this class when
    RBI opens the developer sandbox.

    Apply at: fintech.rbi.org.in
    Contact:  fintech@rbi.org.in
    """

    def __init__(self, api_base_url: str, api_key: str):
        self.api_base = api_base_url
        self.api_key  = api_key
        # TODO: implement when RBI sandbox is available

    def get_wallet(self, wallet_id: str):
        raise NotImplementedError("Connect to RBI Developer Sandbox first")

    def debit_wallet(self, wallet_id, amount_inr, compliance_hash):
        raise NotImplementedError("Connect to RBI Developer Sandbox first")

    def get_fx_quote(self, destination_currency, amount_inr):
        raise NotImplementedError("Connect to RBI Developer Sandbox first")

    def settle(self, *args, **kwargs):
        raise NotImplementedError("Connect to RBI Developer Sandbox first")


# ── Factory ───────────────────────────────────────────────────────────────────

def get_cbdc_engine() -> CBDCEngineBase:
    mode = os.environ.get("CBDC_ENGINE", "simulated")
    if mode == "rbi":
        return CBDCEngineRBI(
            api_base_url=os.environ["RBI_API_URL"],
            api_key=os.environ["RBI_API_KEY"],
        )
    return CBDCEngineSimulated()
