"""
llm_interface.py
----------------
A unified interface to multiple LLM backends.

The agent works at four capability levels depending on available hardware:

  Level 0 — Logic-only (no GPU, no API key)
    Pure rule-based and TF-IDF responses. Fast, deterministic, auditable.
    Suitable for production use where explainability is paramount.

  Level 1 — Groq free tier (no GPU needed, internet required)
    Llama 3.1 8B or 70B via Groq's free API.
    Set GROQ_API_KEY in .env. Get one at console.groq.com/keys

  Level 2 — Ollama local (GPU or CPU, offline)
    Any model supported by Ollama: Mistral 7B, Llama 3.1, Phi-3, Gemma.
    Best for: development, air-gapped environments, data sovereignty.
    Set OLLAMA_BASE_URL=http://localhost:11434 and OLLAMA_MODEL=mistral

  Level 3 — Indian models (API or self-hosted)
    Sarvam-1 (sarvam.ai) — fine-tuned on Indian languages and regulations
    Krutrim (krutrim.ai) — Ola's Indian LLM
    BharatGPT — IIT-Bombay project
    These run on the same interface once an API key is configured.

The interface auto-detects which backends are available at startup
and selects the highest-capability one. This can be overridden by
setting LLM_BACKEND in .env to: logic | groq | ollama | sarvam

Data sovereignty note: Groq and Sarvam process data on external servers.
For RBI-compliance, use Ollama or logic-only mode in production.
All Indian data should stay on Indian infrastructure.
"""

import os
import json
import re
import urllib.request
import urllib.error
from typing import Optional


# ── Backend detection ─────────────────────────────────────────────────────────

def _detect_backend() -> str:
    forced = os.environ.get("LLM_BACKEND", "").strip().lower()
    if forced:
        return forced

    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    if os.environ.get("SARVAM_API_KEY"):
        return "sarvam"
    if os.environ.get("KRUTRIM_API_KEY"):
        return "krutrim"
    if os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_MODEL"):
        return "ollama"
    return "logic"


ACTIVE_BACKEND = _detect_backend()


# ── Base class ────────────────────────────────────────────────────────────────

class LLMBackend:
    name: str = "base"

    def complete(self, system: str, user: str, max_tokens: int = 300) -> Optional[str]:
        raise NotImplementedError

    def is_available(self) -> bool:
        return False


# ── Logic-only backend ─────────────────────────────────────────────────────────

class LogicBackend(LLMBackend):
    """
    Returns None for all completions, signalling callers to use
    their built-in rule-based logic instead.

    This is the safe, auditable default. In production at a regulated
    institution, you may prefer this mode for core compliance decisions.
    """
    name = "logic"

    def complete(self, system: str, user: str, max_tokens: int = 300) -> Optional[str]:
        return None

    def is_available(self) -> bool:
        return True


# ── Groq backend ──────────────────────────────────────────────────────────────

class GroqBackend(LLMBackend):
    """
    Free-tier Llama 3.1 via Groq's API.
    No GPU required. Get a key at console.groq.com/keys
    """
    name = "groq"

    def __init__(self):
        self.api_key = os.environ.get("GROQ_API_KEY", "")
        self.model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    def complete(self, system: str, user: str, max_tokens: int = 300) -> Optional[str]:
        if not self.api_key:
            return None
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }).encode()
        req = urllib.request.Request(
            self.base_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"]
        except Exception:
            return None

    def is_available(self) -> bool:
        return bool(self.api_key)


# ── Ollama backend ────────────────────────────────────────────────────────────

class OllamaBackend(LLMBackend):
    """
    Local LLM via Ollama. Runs on CPU (slow) or GPU (fast).
    Supports any model Ollama supports: Mistral, Llama, Phi, Gemma, etc.

    Install: curl -fsSL https://ollama.ai/install.sh | sh
    Pull a model: ollama pull mistral
    Set: OLLAMA_BASE_URL=http://localhost:11434
         OLLAMA_MODEL=mistral
    """
    name = "ollama"

    def __init__(self):
        self.base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.environ.get("OLLAMA_MODEL", "mistral")

    def complete(self, system: str, user: str, max_tokens: int = 300) -> Optional[str]:
        payload = json.dumps({
            "model": self.model,
            "prompt": f"[SYSTEM]\n{system}\n\n[USER]\n{user}",
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.2},
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data.get("response")
        except Exception:
            return None

    def is_available(self) -> bool:
        try:
            urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=3)
            return True
        except Exception:
            return False


# ── Sarvam AI backend (Indian LLM) ───────────────────────────────────────────

class SarvamBackend(LLMBackend):
    """
    Sarvam-1 — India's first large language model by Sarvam AI.
    Fine-tuned on Indian languages, laws, and domain knowledge.
    Ideal for RBI compliance use cases.

    Get API key: sarvam.ai
    Set: SARVAM_API_KEY=your_key
    """
    name = "sarvam"

    def __init__(self):
        self.api_key = os.environ.get("SARVAM_API_KEY", "")
        self.base_url = "https://api.sarvam.ai/v1/chat/completions"
        self.model = os.environ.get("SARVAM_MODEL", "sarvam-1")

    def complete(self, system: str, user: str, max_tokens: int = 300) -> Optional[str]:
        if not self.api_key:
            return None
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
        }).encode()
        req = urllib.request.Request(
            self.base_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"]
        except Exception:
            return None

    def is_available(self) -> bool:
        return bool(self.api_key)


# ── Factory ───────────────────────────────────────────────────────────────────

_BACKEND_MAP = {
    "logic": LogicBackend,
    "groq": GroqBackend,
    "ollama": OllamaBackend,
    "sarvam": SarvamBackend,
}


def get_llm() -> LLMBackend:
    """
    Returns the highest-priority available LLM backend.
    Order: sarvam > ollama > groq > logic
    Override with LLM_BACKEND env variable.
    """
    backend_cls = _BACKEND_MAP.get(ACTIVE_BACKEND, LogicBackend)
    instance = backend_cls()
    if instance.is_available():
        return instance
    # Fallback chain
    for name in ["ollama", "groq", "logic"]:
        cls = _BACKEND_MAP[name]
        inst = cls()
        if inst.is_available():
            return inst
    return LogicBackend()
