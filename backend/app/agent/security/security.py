"""
security.py
-----------
The e₹ Bridge AI Security Layer.

Protects the agent system from adversarial inputs and misuse.
Every AI request passes through this layer before reaching the agents.

Three subsystems:

1. PROMPT GUARD
   Detects prompt injection attempts — inputs designed to override
   the agent's instructions or extract system prompts.
   Uses a pattern library of known injection techniques.

2. INPUT SANITISER
   Cleans user inputs before they reach the agent.
   Removes control characters, excessive whitespace, and
   characters used in injection attacks.

3. AUDIT LOGGER
   Records every agent interaction — inputs, outputs, risk scores,
   and security events — to an immutable in-memory log.
   In production this writes to a append-only database table
   with cryptographic integrity checks.

Why this matters for RBI:
   The RBI expects that any AI system used in financial services
   maintains a complete audit trail and is protected against
   adversarial manipulation. This layer is the technical implementation
   of those requirements.
"""

import re
import time
import hashlib
import json
from typing import Optional
from collections import deque, defaultdict
from datetime import datetime, timezone


# ── Prompt injection patterns ─────────────────────────────────────────────────
# These are known techniques used to override AI system prompts.
# The list is based on published research into LLM adversarial attacks.

_INJECTION_PATTERNS = [
    # Direct override attempts
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"forget\s+(everything|all|prior)\s+",
    r"disregard\s+(your\s+)?(instructions?|rules?|guidelines?)",
    r"you\s+are\s+now\s+(?!an?\s+e₹)",  # "you are now [something else]"

    # Role injection
    r"act\s+as\s+(if\s+you\s+are\s+)?(?!a|an)\w+",
    r"pretend\s+(to\s+be|you\s+are)\s+",
    r"roleplay\s+as\s+",
    r"you\s+are\s+(?:dan|jailbreak|dev\s+mode|unrestricted)",

    # System prompt extraction
    r"(print|show|reveal|output|display|repeat)\s+(your\s+)?(system\s+prompt|instructions?|rules?)",
    r"what\s+(are\s+your\s+|is\s+your\s+)?(system\s+prompt|instructions?)",
    r"tell\s+me\s+your\s+(hidden\s+)?(prompt|instructions?)",

    # Delimiter injection
    r"---\s*(end\s+of\s+)?(system|instructions?)\s*---",
    r"<\s*/?system\s*>",
    r"\[INST\]|\[/INST\]",
    r"###\s*(instruction|system)",

    # Data extraction
    r"(list|show|dump)\s+(all\s+)?(user\s+)?(data|transactions?|wallets?)",
    r"(access|read|get)\s+(the\s+)?(database|db|all\s+records)",

    # Boundary crossing
    r"sudo\s+",
    r"admin\s*mode",
    r"bypass\s+(security|filter|restriction)",
    r"override\s+(safety|restriction|filter)",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _INJECTION_PATTERNS]


# ── Rate limiting ─────────────────────────────────────────────────────────────

class RateLimiter:
    """
    Token-bucket rate limiter per session ID.
    Defaults: 30 requests per minute per session.
    """
    def __init__(self, limit: int = 30, window_seconds: int = 60):
        self.limit = limit
        self.window = window_seconds
        self._buckets: dict[str, deque] = defaultdict(deque)

    def is_allowed(self, session_id: str) -> tuple[bool, int]:
        """Returns (allowed, remaining)."""
        now = time.time()
        bucket = self._buckets[session_id]
        # Remove timestamps outside the window
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False, 0
        bucket.append(now)
        return True, self.limit - len(bucket)


# ── Audit logger ──────────────────────────────────────────────────────────────

class AuditLogger:
    """
    Immutable audit trail for all AI agent interactions.

    Each entry is hashed with the previous entry's hash (chain-of-custody).
    This makes tampering detectable — any modification breaks the chain.

    In production, entries are written to a PostgreSQL table with:
      - Append-only permissions (no UPDATE or DELETE)
      - Row-level checksums
      - Signed timestamps from a trusted time source
    """
    def __init__(self):
        self._log: list[dict] = []
        self._prev_hash = "genesis"

    def record(
        self,
        event_type: str,
        session_id: str,
        input_text: str,
        output_text: str,
        metadata: Optional[dict] = None,
    ) -> str:
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = {
            "event_type": event_type,
            "session_id": session_id,
            "timestamp": timestamp,
            "input_hash": hashlib.sha256(input_text.encode()).hexdigest()[:16],
            "output_hash": hashlib.sha256(output_text.encode()).hexdigest()[:16],
            "metadata": metadata or {},
            "prev_hash": self._prev_hash,
        }
        raw = json.dumps(entry, sort_keys=True)
        entry_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]
        entry["hash"] = entry_hash
        self._prev_hash = entry_hash
        self._log.append(entry)
        return entry_hash

    def get_recent(self, n: int = 20) -> list[dict]:
        return self._log[-n:]

    def verify_chain(self) -> bool:
        """Checks that the audit chain is intact (no tampering)."""
        prev = "genesis"
        for entry in self._log:
            test = {k: v for k, v in entry.items() if k != "hash"}
            test["prev_hash"] = prev
            raw = json.dumps(test, sort_keys=True)
            expected = hashlib.sha256(raw.encode()).hexdigest()[:16]
            if entry.get("hash") != expected:
                return False
            prev = entry["hash"]
        return True

    @property
    def total_events(self) -> int:
        return len(self._log)


# ── Input sanitiser ───────────────────────────────────────────────────────────

def sanitise_input(text: str) -> str:
    """
    Cleans user input before it reaches the agent.
    Removes control characters, truncates excessively long inputs,
    and normalises whitespace.
    """
    if not isinstance(text, str):
        return ""
    # Remove null bytes and control characters (except newlines and tabs)
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)
    # Collapse excessive whitespace
    text = re.sub(r"\s{4,}", "   ", text)
    # Truncate to a safe maximum
    return text[:2000]


# ── Main security filter ──────────────────────────────────────────────────────

class SecurityFilter:
    """
    Entry point for the AI security layer.
    Call check() on every user input before passing it to the agent.
    """

    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.audit_logger = AuditLogger()
        self._blocked_sessions: set[str] = set()

    def check(
        self, text: str, session_id: str = "default"
    ) -> dict:
        """
        Validates a user input.

        Returns:
            {
                "allowed": True/False,
                "clean_text": sanitised input,
                "threat_detected": True/False,
                "threat_type": "injection" | "rate_limit" | "blocked" | None,
                "threat_detail": str or None,
                "audit_hash": str,
            }
        """
        # 1. Blocked session check
        if session_id in self._blocked_sessions:
            audit_hash = self.audit_logger.record(
                "BLOCKED_SESSION", session_id, text[:50], "rejected"
            )
            return {
                "allowed": False,
                "clean_text": "",
                "threat_detected": True,
                "threat_type": "blocked",
                "threat_detail": "Session has been blocked due to prior security violation.",
                "audit_hash": audit_hash,
            }

        # 2. Rate limit check
        allowed, remaining = self.rate_limiter.is_allowed(session_id)
        if not allowed:
            audit_hash = self.audit_logger.record(
                "RATE_LIMITED", session_id, text[:50], "rejected"
            )
            return {
                "allowed": False,
                "clean_text": "",
                "threat_detected": True,
                "threat_type": "rate_limit",
                "threat_detail": "Rate limit exceeded. Maximum 30 requests per minute.",
                "audit_hash": audit_hash,
            }

        # 3. Sanitise
        clean = sanitise_input(text)

        # 4. Injection detection
        for pattern in _COMPILED_PATTERNS:
            match = pattern.search(clean)
            if match:
                # Block the session after a prompt injection attempt
                self._blocked_sessions.add(session_id)
                audit_hash = self.audit_logger.record(
                    "INJECTION_DETECTED",
                    session_id,
                    text[:100],
                    "blocked",
                    {"pattern": pattern.pattern[:60], "match": match.group()[:60]},
                )
                return {
                    "allowed": False,
                    "clean_text": "",
                    "threat_detected": True,
                    "threat_type": "injection",
                    "threat_detail": f"Prompt injection attempt detected. Session blocked.",
                    "audit_hash": audit_hash,
                }

        # 5. Clean pass
        audit_hash = self.audit_logger.record(
            "INPUT_ACCEPTED", session_id, clean[:50], "passed"
        )
        return {
            "allowed": True,
            "clean_text": clean,
            "threat_detected": False,
            "threat_type": None,
            "threat_detail": None,
            "audit_hash": audit_hash,
        }

    def get_audit_log(self, n: int = 20) -> list[dict]:
        return self.audit_logger.get_recent(n)

    def get_stats(self) -> dict:
        return {
            "total_events": self.audit_logger.total_events,
            "blocked_sessions": len(self._blocked_sessions),
            "chain_intact": self.audit_logger.verify_chain(),
        }
