# GPU Requirements for the e₹ Bridge AI Agent

## Overview

The e₹ Bridge AI agent is designed to run at four capability levels.
You choose the level based on your budget, latency requirements, and
data sovereignty needs. The system works at every level — including
Level 0 with no GPU at all.

---

## Level 0 — No GPU (runs today, free)

**What works:** Full FEMA classification, risk scoring, and RAG-based Q&A.
All three agents run on CPU using TF-IDF and rule-based logic.

**Hardware:** Any laptop or cloud VM. 2GB RAM minimum.

**Performance:** < 50ms per request.

**Best for:** PoC demonstration, regulatory sandbox submissions,
development, and any environment where explainability is the
priority over conversational fluency.

**Cost:** ₹0.

---

## Level 1 — Groq free tier (no GPU, internet required)

**What works:** Level 0 + natural language generation from Llama 3.1 70B.
The agent's reasoning steps and final answers are phrased naturally
rather than assembled from structured templates.

**Hardware:** Any machine with internet access.

**Setup:**
```bash
# Get a free key at console.groq.com/keys
echo "GROQ_API_KEY=gsk_your_key" >> .env
```

**Performance:** 200–600ms per request (network latency dependent).

**Best for:** Development and demos where you want conversational
quality without purchasing hardware.

**Cost:** Free up to Groq's rate limits (roughly 30 requests/minute
on the free tier as of 2025).

**Data note:** Queries are processed on Groq's US-based servers.
Not suitable for live customer data in a production RBI deployment.

---

## Level 2 — Single GPU workstation (offline, full control)

Run any open-source model locally via Ollama. No internet required.
All data stays on your machine — appropriate for RBI-compliant
production environments.

### Recommended GPU: NVIDIA RTX 4090

| Spec | Value |
|------|-------|
| VRAM | 24 GB |
| Architecture | Ada Lovelace |
| Price (India) | ₹1.8L – ₹2.2L |
| Power | 450W |

**Models it runs comfortably:**
- Mistral 7B — best balance of speed and quality for regulatory Q&A
- Llama 3.1 8B — strong reasoning, multilingual support
- Phi-3 Mini (3.8B) — fastest, good for classification tasks
- Gemma 9B — Google's model, strong on factual Q&A

**Setup:**
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model (Mistral recommended for regulatory use)
ollama pull mistral

# Configure the agent
echo "OLLAMA_BASE_URL=http://localhost:11434" >> .env
echo "OLLAMA_MODEL=mistral" >> .env
```

**Performance:** 20–80 tokens/second depending on model.

---

### Alternative: AMD Radeon RX 7900 XTX

| Spec | Value |
|------|-------|
| VRAM | 24 GB |
| Price (India) | ₹1.4L – ₹1.7L |
| Notes | Cheaper than RTX 4090; Ollama supports ROCm |

---

## Level 3 — Multi-GPU server (production quality)

For running 70B parameter models at production latency,
or for running multiple agent instances concurrently.

### Recommended: 2× NVIDIA A100 80GB

| Spec | Value |
|------|-------|
| VRAM total | 160 GB (2× 80 GB) |
| Architecture | Ampere |
| Price (India) | ₹40L – ₹55L (used/refurb) |
| Power | 2× 400W |
| NVLink | Yes — GPUs communicate at full bandwidth |

**Models it runs:**
- Llama 3.1 70B — most capable open model for regulatory reasoning
- Mistral Large — strong on multilingual and structured data
- Sarvam-1 (when self-hosted) — Indian-specific fine-tuning

**Performance:** Llama 3.1 70B at 30–50 tokens/second.

---

### Recommended: 2× NVIDIA H100 80GB SXM

| Spec | Value |
|------|-------|
| VRAM total | 160 GB |
| Architecture | Hopper |
| Price (India) | ₹1.2Cr – ₹1.8Cr |
| Notes | Best-in-class; used by top Indian banks and NPCI |

**Use this if:** You are deploying at a bank, running inference for
millions of users, or training/fine-tuning your own models.

---

## Level 4 — Indian LLM models (recommended for production)

These models are built specifically for Indian languages and
regulatory contexts. They outperform generic English models on
FEMA codes, RBI regulations, and Hindi-language queries.

### Sarvam-1

| Detail | Value |
|--------|-------|
| Developer | Sarvam AI, Bengaluru |
| Parameters | 7B (approx) |
| Training | Indian languages + legal/regulatory corpus |
| API | sarvam.ai (cloud) or self-hostable |
| GPU needed | RTX 4090 or A100 for self-hosting |
| Setup | `echo "SARVAM_API_KEY=your_key" >> .env` |

**Why use it:** Fine-tuned on Indian languages and domain knowledge.
Better than generic Llama on questions about Indian regulations,
regional banking practices, and Hindi/Hinglish queries from NRIs.

---

### Krutrim (Ola)

| Detail | Value |
|--------|-------|
| Developer | Ola AI, Bengaluru |
| Focus | Indian cultural and regulatory context |
| API | krutrim.ai |
| Setup | `echo "KRUTRIM_API_KEY=your_key" >> .env` |

---

### BharatGPT (IIT Bombay / CDAC)

Government-backed Indian LLM research project.
Not yet publicly API-accessible as of mid-2025.
Watch: bharatgpt.gov.in

---

## Cloud GPU options (India region, data sovereignty)

For production deployments where data must stay in India:

| Provider | GPU | Notes |
|----------|-----|-------|
| AWS Mumbai (ap-south-1) | A100, H100 | p4d, p5 instances |
| Azure India Central | A100 | NC series |
| Google Cloud Mumbai | A100, H100 | a2-highgpu series |
| Jio Cloud | GPU available | Data stays in India |
| E2E Networks | A100 | Indian startup, good pricing |
| CoreWeave India | H100 | New, competitive pricing |

**Recommended for a bank deployment:** E2E Networks or AWS Mumbai.
Both offer dedicated GPU instances with data residency guarantees.

---

## Summary: What to buy for each use case

| Use case | Hardware | Cost (India) | LLM |
|----------|----------|-------------|-----|
| PoC / demo | Laptop (no GPU) | ₹0 extra | Logic-only or Groq free |
| RBIH Showcase | RTX 4090 workstation | ₹2L | Mistral 7B local |
| Bank pilot | 2× A100 80GB server | ₹50L | Llama 3.1 70B |
| Production bank | 4× H100 80GB | ₹2.5Cr | Sarvam-1 / Llama 70B |
| National scale (NPCI) | 8× H100 cluster | ₹5Cr+ | Fine-tuned Sarvam / custom |

---

## India's AI GPU landscape

India's government has committed ₹10,000 crore to the India AI Mission,
which includes a 10,000 GPU compute cluster available to Indian startups
and researchers at subsidised rates. Access via: indiaai.gov.in/compute

NASSCOM's AI Cloud (AIRAWAT) at C-DAC Pune also provides GPU compute
for Indian AI projects. This is the most cost-effective route for a
startup building on e-Rupee — you may be eligible for subsidised access
given the CBDC / RBI alignment.

Contact: airawat@cdac.in
