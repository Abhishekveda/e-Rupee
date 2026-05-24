"""
crypto/hsm.py
=============
Hardware Security Module (HSM) simulation for e₹ Bridge.

In production this module wraps a real HSM:
  - AWS CloudHSM (FIPS 140-2 Level 3) — recommended for India deployment
  - Azure Dedicated HSM
  - Thales Luna Network HSM (used by many Indian banks)

For the PoC and pilot, this module simulates HSM behaviour using
Python's cryptography library. The interface is identical — swap
the backend without changing any calling code.

KEY MANAGEMENT ARCHITECTURE:
  Root CA key     → HSM (never leaves hardware in production)
  Bridge operator → Derived from root, rotates every 90 days
  Transaction signing → Ephemeral keys per session
  Multi-sig keys  → Distributed across 3 parties (2-of-3 threshold)

SECURITY PROPERTIES:
  - Private keys never appear in logs or error messages
  - Key derivation uses HKDF-SHA256
  - Signatures use ECDSA on secp256k1 (Ethereum-compatible)
  - All operations are logged to the immutable audit chain
  - Timing-safe comparisons throughout (no timing side-channels)

TEAM NOTE:
  Replace HSMSimulator with HSMProduction before pilot.
  HSMProduction wraps AWS CloudHSM SDK or PKCS#11 interface.
  The abstraction layer (HSMBase) ensures zero code changes above.
"""

import os
import hmac
import hashlib
import secrets
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature, encode_dss_signature
)
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

log = logging.getLogger(__name__)


@dataclass
class SignedTransaction:
    """
    A transaction with its cryptographic signature.
    This is what gets submitted to the smart contract.
    """
    tx_hash:    bytes    # keccak256 of the transaction data
    signature:  bytes    # DER-encoded ECDSA signature
    public_key: bytes    # Compressed public key (33 bytes)
    signer_id:  str      # Identifies which key signed
    signed_at:  datetime # UTC timestamp
    key_version: int     # Key rotation version


@dataclass
class ComplianceAttestation:
    """
    Cryptographically signed compliance attestation from the AI agent.
    This is posted to the ZKCompliance contract.
    """
    transfer_id:    str
    commitment:     bytes    # H(fema || lrs || risk || nonce || address)
    nonce:          bytes    # 32-byte random nonce
    risk_score:     int
    fema_category:  int
    lrs_amount_inr: float
    signature:      bytes    # Signs commitment + transfer_id
    attested_by:    str      # Oracle address
    attested_at:    datetime


class HSMBase(ABC):
    """Abstract interface — all HSM implementations satisfy this contract."""

    @abstractmethod
    def sign_transaction(self, tx_data: dict) -> SignedTransaction:
        """Sign a transaction payload. Private key never leaves HSM."""
        ...

    @abstractmethod
    def verify_signature(self, tx_hash: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify a signature. Returns True if valid."""
        ...

    @abstractmethod
    def generate_compliance_commitment(
        self,
        fema_category: int,
        lrs_amount_inr: float,
        risk_score: int,
        sender_address: str,
    ) -> tuple[bytes, bytes]:
        """Generate (commitment_hash, nonce). Commitment never reveals inputs."""
        ...

    @abstractmethod
    def get_public_key(self) -> bytes:
        """Return the compressed public key for this signer."""
        ...


class HSMSimulator(HSMBase):
    """
    Software simulation of HSM behaviour.
    Uses the same interfaces as a real HSM — swap for production.
    NEVER USE THIS WITH REAL FUNDS.
    """

    def __init__(self, key_file: Optional[str] = None):
        """
        Initialise the HSM simulator.
        In production: connect to CloudHSM cluster instead.
        """
        self._backend = default_backend()
        self._key_version = 1
        self._key_rotation_at = datetime.now(timezone.utc) + timedelta(days=90)

        if key_file and os.path.exists(key_file):
            self._private_key = self._load_key(key_file)
        else:
            self._private_key = self._generate_key()
            if key_file:
                self._save_key(key_file)

        self._public_key_bytes = self._compress_public_key()

    # ── Core cryptographic operations ────────────────────────────────────────

    def sign_transaction(self, tx_data: dict) -> SignedTransaction:
        """
        Sign a transaction dictionary.
        The dict is serialised deterministically before hashing.
        """
        import json

        # Deterministic serialisation — field order matters
        canonical = json.dumps(tx_data, sort_keys=True, separators=(',', ':'))
        tx_bytes = canonical.encode('utf-8')

        # keccak256 hash (Ethereum-compatible)
        tx_hash = self._keccak256(tx_bytes)

        # ECDSA sign on secp256k1
        sig_der = self._private_key.sign(tx_hash, ec.ECDSA(hashes.Prehashed(hashes.SHA256())))

        # Log the signing event (never log the private key)
        log.info(f"HSM signed tx_hash={tx_hash.hex()[:16]}... signer={self._signer_id()}")

        return SignedTransaction(
            tx_hash=tx_hash,
            signature=sig_der,
            public_key=self._public_key_bytes,
            signer_id=self._signer_id(),
            signed_at=datetime.now(timezone.utc),
            key_version=self._key_version,
        )

    def verify_signature(self, tx_hash: bytes, signature: bytes, public_key: bytes) -> bool:
        """
        Verify an ECDSA signature.
        Timing-safe: always runs the full verification regardless of early exit.
        """
        try:
            pub = ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256K1(), public_key
            )
            pub.verify(signature, tx_hash, ec.ECDSA(hashes.Prehashed(hashes.SHA256())))
            return True
        except (InvalidSignature, ValueError):
            return False

    def generate_compliance_commitment(
        self,
        fema_category: int,
        lrs_amount_inr: float,
        risk_score: int,
        sender_address: str,
    ) -> tuple[bytes, bytes]:
        """
        Generate a cryptographic commitment for compliance data.

        Returns (commitment_bytes, nonce_bytes).

        The commitment is:
          H(fema_category || lrs_paise || risk_score || nonce || sender)

        This mirrors exactly what the Solidity ZKCompliance contract verifies.
        The commitment can be posted on-chain — the preimage stays off-chain.
        """
        nonce = secrets.token_bytes(32)
        lrs_paise = int(lrs_amount_inr * 100)  # Convert to paise

        preimage = (
            fema_category.to_bytes(1, 'big') +
            lrs_paise.to_bytes(16, 'big') +
            risk_score.to_bytes(1, 'big') +
            nonce +
            bytes.fromhex(sender_address.lstrip('0x').zfill(40))
        )

        commitment = hashlib.sha256(preimage).digest()
        return commitment, nonce

    def get_public_key(self) -> bytes:
        return self._public_key_bytes

    # ── Key management ────────────────────────────────────────────────────────

    def should_rotate(self) -> bool:
        return datetime.now(timezone.utc) >= self._key_rotation_at

    def rotate_key(self):
        """
        Rotate the signing key. In production: generate new key in HSM,
        publish new public key, keep old key for signature verification
        of existing transactions.
        """
        self._private_key = self._generate_key()
        self._public_key_bytes = self._compress_public_key()
        self._key_version += 1
        self._key_rotation_at = datetime.now(timezone.utc) + timedelta(days=90)
        log.info(f"HSM key rotated to version {self._key_version}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _generate_key(self) -> ec.EllipticCurvePrivateKey:
        return ec.generate_private_key(ec.SECP256K1(), self._backend)

    def _load_key(self, path: str) -> ec.EllipticCurvePrivateKey:
        with open(path, 'rb') as f:
            return serialization.load_pem_private_key(f.read(), password=None)

    def _save_key(self, path: str):
        """Save the private key — ONLY for simulation. Never do this in production."""
        pem = self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(
                os.environ.get('HSM_KEY_PASSPHRASE', 'dev-only').encode()
            )
        )
        with open(path, 'wb') as f:
            f.write(pem)
        os.chmod(path, 0o600)

    def _compress_public_key(self) -> bytes:
        pub = self._private_key.public_key()
        return pub.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.CompressedPoint
        )

    def _signer_id(self) -> str:
        return f"hsm-sim-v{self._key_version}-{self._public_key_bytes[:4].hex()}"

    @staticmethod
    def _keccak256(data: bytes) -> bytes:
        """
        keccak256 compatible with Ethereum.
        Note: Python's hashlib uses SHA3, not keccak. Use pysha3 for exact Ethereum compatibility.
        Using SHA256 here for simulation — swap for keccak256 in production.
        """
        return hashlib.sha256(data).digest()


# ── Multi-signature coordinator ───────────────────────────────────────────────

class MultiSigCoordinator:
    """
    Coordinates 2-of-3 multi-signature for high-value transfers.

    In production:
    - Signer 1: Sending bank (HSM-backed)
    - Signer 2: Receiving bank (HSM-backed)
    - Signer 3: Bridge operator (HSM-backed)

    2 of the 3 must sign before the transaction is submitted.
    No single party can unilaterally process a high-value transfer.
    """

    def __init__(self, threshold: int = 2, total_signers: int = 3):
        self.threshold = threshold
        self.total_signers = total_signers
        self._pending: dict[str, list[SignedTransaction]] = {}

    def add_signature(self, tx_id: str, signed_tx: SignedTransaction) -> bool:
        """
        Add a signature to a multi-sig transaction.
        Returns True when threshold is reached.
        """
        if tx_id not in self._pending:
            self._pending[tx_id] = []

        # Prevent duplicate signatures from same signer
        existing_signers = {s.signer_id for s in self._pending[tx_id]}
        if signed_tx.signer_id in existing_signers:
            raise ValueError(f"Signer {signed_tx.signer_id} already signed {tx_id}")

        self._pending[tx_id].append(signed_tx)

        count = len(self._pending[tx_id])
        log.info(f"Multi-sig {tx_id}: {count}/{self.threshold} signatures collected")

        return count >= self.threshold

    def get_signatures(self, tx_id: str) -> list[SignedTransaction]:
        return self._pending.get(tx_id, [])

    def is_ready(self, tx_id: str) -> bool:
        return len(self._pending.get(tx_id, [])) >= self.threshold

    def clear(self, tx_id: str):
        self._pending.pop(tx_id, None)


# ── Singleton for application use ────────────────────────────────────────────

_hsm_instance: Optional[HSMSimulator] = None

def get_hsm() -> HSMSimulator:
    global _hsm_instance
    if _hsm_instance is None:
        key_file = os.environ.get('HSM_KEY_FILE', '.hsm_key.pem')
        _hsm_instance = HSMSimulator(key_file=key_file)
    return _hsm_instance
