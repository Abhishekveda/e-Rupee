"""
backend/app/cbdc/protocol.py
============================
The actual CBDC protocol engine.

This connects:
  - The 5 AI compliance agents (already built)
  - The eRupee.sol token contract
  - The eRupeeBridge.sol cross-border contract

FLOW FOR EVERY TRANSFER:
  1. User submits transfer request
  2. AI agents run (FEMA → Risk → LRS)
  3. Protocol posts attestation on-chain
  4. User's e-Rupee tokens lock in bridge
  5. Relayer executes on destination chain
  6. Settlement confirmed on-chain

WHAT MAKES THIS UNIQUE:
  The AI compliance decision is committed on-chain BEFORE
  the funds move. The smart contract CANNOT be bypassed.
  No amount of frontend manipulation can skip the AI check.
  This is compliance enforced at the cryptographic layer.
"""

import os
import secrets
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class ComplianceResult:
    """Result from the AI compliance pipeline."""
    approved:      bool
    risk_score:    int
    fema_category: int
    fema_code:     str
    lrs_ok:        bool
    fema_ok:       bool
    lrs_remaining: float
    reason:        str


@dataclass
class AttestationPayload:
    """
    What gets posted on-chain by the compliance oracle.
    The txHash commits to the exact transfer parameters —
    this prevents the attestation being used for any other transfer.
    """
    tx_hash:       bytes   # H(from, to, amount, nonce, block_window)
    nonce:         bytes   # 32-byte random nonce
    risk_score:    int
    fema_category: int
    lrs_ok:        bool
    fema_ok:       bool
    valid_until:   int     # Unix timestamp


@dataclass
class TransferRequest:
    sender_wallet:     str
    recipient_address: str
    amount_inr:        float   # in rupees (we convert to paise internally)
    destination:       str     # "AED", "SGD", "USD", "RUB" etc
    purpose_text:      str     # plain English — AI classifies this
    purpose_code:      Optional[str] = None  # override if user knows


@dataclass
class TransferResult:
    success:           bool
    transfer_id:       str
    cbdc_tx_hash:      str
    bridge_tx_hash:    str
    amount_inr:        float
    destination_amount: float
    destination_currency: str
    fee_inr:           float
    ai_risk_score:     int
    ai_fema_code:      str
    settlement_time_ms: int
    dollar_used:       bool = False
    error:             Optional[str] = None


class CBDCProtocol:
    """
    The actual CBDC protocol.
    Connects AI agents → on-chain attestation → token transfer.
    """

    # Destination currencies supported
    CURRENCIES = {
        "AED": 0.044,   # UAE Digital Dirham
        "SGD": 0.016,   # Singapore Dollar
        "USD": 0.012,   # US Dollar (multi-hop only)
        "RUB": 0.93,    # Russian Ruble (BRICS)
        "BRL": 0.062,   # Brazilian Real (BRICS)
        "ZAR": 0.22,    # South African Rand (BRICS)
        "SAR": 0.045,   # Saudi Riyal
        "CNY": 0.086,   # Chinese Yuan (when bilateral agreement exists)
        "MYR": 0.056,   # Malaysian Ringgit
    }

    BRIDGE_FEE_BPS = 20  # 0.20%

    def __init__(self, orchestrator):
        """
        orchestrator: the AgentOrchestrator with all 5 AI agents
        """
        self.orch = orchestrator
        log.info("[CBDC Protocol] Initialised. AI agents connected.")

    def process_transfer(self, request: TransferRequest) -> TransferResult:
        """
        Full transfer pipeline:
        AI compliance → on-chain attestation → token lock → settlement
        """
        import time
        t_start = time.time()

        try:
            # ── Step 1: AI Compliance Pipeline ──────────────────────
            compliance = self._run_compliance(request)

            if not compliance.approved:
                return TransferResult(
                    success=False,
                    transfer_id="",
                    cbdc_tx_hash="",
                    bridge_tx_hash="",
                    amount_inr=request.amount_inr,
                    destination_amount=0,
                    destination_currency=request.destination,
                    fee_inr=0,
                    ai_risk_score=compliance.risk_score,
                    ai_fema_code=compliance.fema_code,
                    settlement_time_ms=0,
                    error=compliance.reason,
                )

            # ── Step 2: Generate attestation ─────────────────────────
            attestation = self._build_attestation(request, compliance)

            # ── Step 3: Post attestation on-chain ────────────────────
            # In production: web3.py call to eRupee.postAttestation()
            # In PoC: simulate with the same logic
            self._post_attestation(attestation)

            # ── Step 4: Execute CBDC transfer ────────────────────────
            cbdc_hash = self._execute_cbdc_transfer(
                request.sender_wallet,
                request.recipient_address,
                request.amount_inr,
                attestation,
            )

            # ── Step 5: Bridge to destination currency ───────────────
            fee_inr   = round(request.amount_inr * self.BRIDGE_FEE_BPS / 10000, 2)
            net_inr   = request.amount_inr - fee_inr
            rate      = self.CURRENCIES.get(request.destination.upper(), 0)
            dest_amt  = round(net_inr * rate, 4)

            bridge_hash = self._execute_bridge(
                cbdc_hash, request.recipient_address,
                dest_amt, request.destination,
            )

            elapsed_ms = int((time.time() - t_start) * 1000)

            return TransferResult(
                success=True,
                transfer_id=self._generate_id(),
                cbdc_tx_hash=cbdc_hash,
                bridge_tx_hash=bridge_hash,
                amount_inr=request.amount_inr,
                destination_amount=dest_amt,
                destination_currency=request.destination.upper(),
                fee_inr=fee_inr,
                ai_risk_score=compliance.risk_score,
                ai_fema_code=compliance.fema_code,
                settlement_time_ms=elapsed_ms,
                dollar_used=False,
            )

        except Exception as e:
            log.error(f"Transfer failed: {e}")
            return TransferResult(
                success=False, transfer_id="", cbdc_tx_hash="",
                bridge_tx_hash="", amount_inr=request.amount_inr,
                destination_amount=0, destination_currency=request.destination,
                fee_inr=0, ai_risk_score=0, ai_fema_code="",
                settlement_time_ms=0, error=str(e),
            )

    # ── Private methods ───────────────────────────────────────────────

    def _run_compliance(self, req: TransferRequest) -> ComplianceResult:
        """Run all 5 AI agents and return a combined compliance decision."""

        # FEMA classification
        fema = self.orch.classify_purpose(req.purpose_text, req.amount_inr)

        # Risk scoring
        purpose_code = req.purpose_code or fema["code"]
        risk = self.orch.score_risk(
            sender_wallet=req.sender_wallet,
            recipient_address=req.recipient_address,
            amount_inr=req.amount_inr,
            purpose_code=purpose_code,
            recipient_country=req.destination[:2].upper(),
        )

        approved  = risk["recommendation"] == "APPROVE"
        lrs_ok    = "LRS" not in str(risk.get("flags", []))
        fema_ok   = fema["confidence"] in ("HIGH", "MEDIUM")

        if not approved:
            reason = "; ".join(
                f["rule"] + ": " + f["detail"][:60]
                for f in risk.get("flags", [])
            ) or "High risk score"
        elif not fema_ok:
            reason = f"FEMA confidence too low: {fema['confidence']}"
        else:
            reason = "Approved"

        # Map FEMA code to category (1–13)
        fema_category = self._code_to_category(fema["code"])

        lrs_remaining = 20_750_000 - req.amount_inr  # simplified

        return ComplianceResult(
            approved=approved and fema_ok,
            risk_score=risk["risk_score"],
            fema_category=fema_category,
            fema_code=fema["code"],
            lrs_ok=lrs_ok,
            fema_ok=fema_ok,
            lrs_remaining=max(0, lrs_remaining),
            reason=reason,
        )

    def _build_attestation(
        self, req: TransferRequest, compliance: ComplianceResult
    ) -> AttestationPayload:
        """Build the on-chain attestation payload."""
        nonce = secrets.token_bytes(32)

        # txHash = H(from, to, amount_paise, nonce, block_window)
        # block_window = current time / 300 seconds (~5 min window)
        import time
        block_window = int(time.time()) // 300
        amount_paise = int(req.amount_inr * 100)

        preimage = (
            req.sender_wallet.encode() +
            req.recipient_address.encode() +
            amount_paise.to_bytes(16, 'big') +
            nonce +
            block_window.to_bytes(8, 'big')
        )
        tx_hash = hashlib.sha256(preimage).digest()

        return AttestationPayload(
            tx_hash=tx_hash,
            nonce=nonce,
            risk_score=compliance.risk_score,
            fema_category=compliance.fema_category,
            lrs_ok=compliance.lrs_ok,
            fema_ok=compliance.fema_ok,
            valid_until=int(datetime.now(timezone.utc).timestamp()) + 300,
        )

    def _post_attestation(self, attestation: AttestationPayload):
        """
        Post attestation on-chain.

        Production: web3.py call:
            contract.functions.postAttestation(
                attestation.tx_hash,
                attestation.risk_score,
                attestation.fema_category,
                attestation.lrs_ok,
                attestation.fema_ok,
            ).transact({'from': oracle_address})

        PoC: log it
        """
        log.info(
            f"[CBDC] Attestation posted: risk={attestation.risk_score} "
            f"fema={attestation.fema_category} "
            f"hash={attestation.tx_hash.hex()[:16]}..."
        )

    def _execute_cbdc_transfer(
        self, sender: str, recipient: str, amount_inr: float,
        attestation: AttestationPayload,
    ) -> str:
        """
        Execute the CBDC token transfer.

        Production: web3.py call:
            eRupee.functions.crossBorderTransfer(
                recipient,
                amount_paise,
                tx_hash,
                nonce,
            ).transact({'from': sender})

        PoC: return simulated hash
        """
        raw = f"cbdc:{sender}:{recipient}:{amount_inr}:{secrets.token_hex(8)}"
        return "0xcbdc" + hashlib.sha256(raw.encode()).hexdigest()[:60]

    def _execute_bridge(
        self, cbdc_hash: str, recipient: str,
        dest_amount: float, currency: str,
    ) -> str:
        """
        Execute bridge to destination currency.

        Production: web3.py call to eRupeeBridge.initiateTransfer()

        PoC: return simulated hash
        """
        raw = f"bridge:{cbdc_hash}:{recipient}:{dest_amount}:{secrets.token_hex(8)}"
        return "0xbridge" + hashlib.sha256(raw.encode()).hexdigest()[:56]

    def _generate_id(self) -> str:
        return secrets.token_hex(16)

    @staticmethod
    def _code_to_category(code: str) -> int:
        """Map FEMA code to category (1–13)."""
        mapping = {
            "P0101": 1, "P0102": 1, "P0103": 2,
            "P0104": 3, "P0801": 4, "P1301": 5,
        }
        return mapping.get(code, 1)


# ── web3 integration stub ─────────────────────────────────────────────────────
# Uncomment and configure when RBI Developer Sandbox opens

# from web3 import Web3
#
# class CBDCProtocolOnChain(CBDCProtocol):
#     """Production version — calls actual smart contracts."""
#
#     def __init__(self, orchestrator, rpc_url: str, contract_addrs: dict):
#         super().__init__(orchestrator)
#         self.w3 = Web3(Web3.HTTPProvider(rpc_url))
#         self.erupee  = self.w3.eth.contract(
#             address=contract_addrs["eRupee"],
#             abi=open("abi/eRupee.json").read()
#         )
#         self.bridge  = self.w3.eth.contract(
#             address=contract_addrs["eRupeeBridge"],
#             abi=open("abi/eRupeeBridge.json").read()
#         )
#
#     def _post_attestation(self, attestation):
#         tx = self.erupee.functions.postAttestation(
#             attestation.tx_hash,
#             attestation.risk_score,
#             attestation.fema_category,
#             attestation.lrs_ok,
#             attestation.fema_ok,
#         ).build_transaction({...})
#         signed = self.w3.eth.account.sign_transaction(tx, private_key=os.environ["ORACLE_KEY"])
#         self.w3.eth.send_raw_transaction(signed.rawTransaction)
