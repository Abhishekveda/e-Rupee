# e₹ Bridge — Architecture & AI Agent Documentation

**Version 2.0 — Custom AI Agent · RBIH Bank-Fintech Showcase 2026**

🌐 Live Demo: https://abhishekveda.github.io/E-Rupee

---

## What's New in v2.0: Custom AI Agent

Version 2.0 replaces any third-party AI API with a **fully custom AI agent** built entirely in Python. It runs locally with zero external dependencies.

### Why a custom agent instead of an API?

| | Third-party AI API | e₹ Custom AI Agent |
|-|--------------------|--------------------|
| Dependency | External service | Zero — runs locally |
| Explainability | Black box | Every decision has named rules |
| RBI auditability | Cannot audit | Full source code in repo |
| Cost | Per-call pricing | Free — stdlib only |
| Offline use | No | Yes |
| Customisable | Limited | Fully — edit knowledge_base.py |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: SENDER                                                             │
│  Indian diaspora user with e-Rupee retail wallet (e₹-R)                    │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────────────┐
│  LAYER 2: e₹ AI AGENT (custom — no external API)                           │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  ORCHESTRATOR  (orchestrator.py)                                     │  │
│  │  Routes requests to sub-agents, manages session state               │  │
│  └──────┬─────────────────────┬────────────────────┬────────────────────┘  │
│         │                     │                    │                        │
│  ┌──────▼──────┐   ┌──────────▼──────┐   ┌────────▼────────────────────┐  │
│  │ FEMA AGENT  │   │  RISK AGENT     │   │  Q&A AGENT                  │  │
│  │             │   │                 │   │                              │  │
│  │ TF-IDF +    │   │ Rule-based +    │   │ RAG over RBI knowledge base  │  │
│  │ keyword     │   │ statistical     │   │ 12 regulatory chunks         │  │
│  │ matching    │   │ scoring (0-100) │   │ Optional: Groq Llama 3.1    │  │
│  │             │   │ 8 named rules   │   │ (free tier)                  │  │
│  └─────────────┘   └─────────────────┘   └──────────────────────────────┘  │
│                                                                             │
│  Knowledge base: FEMA codes + RBI circulars + LRS rules (knowledge_base.py)│
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────────────┐
│  LAYER 3: CBDC BRIDGE                                                       │
│  FastAPI backend simulating RBI e-Rupee API                                 │
│  Wallet debit → FX oracle → CBDC hash → Ethereum bridge relay              │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────────────┐
│  LAYER 4: SETTLEMENT                                                        │
│  CBDCBridge.sol on Ethereum Sepolia testnet                                 │
│  mAED / mSGD stablecoins credited to recipient                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## AI Agent — Three Sub-Agents

### Sub-Agent 1: FEMA Classification Agent (`fema_agent.py`)

**What it does:** Classifies remittance purpose from plain English into the correct FEMA purpose code.

**How it works (no external AI):**
1. **Keyword matching** — each FEMA code has associated keywords; fast O(1) match
2. **TF-IDF cosine similarity** — semantic matching against all 13 FEMA code descriptions
3. **Confidence scoring** — HIGH (>0.55), MEDIUM (>0.25), LOW (<0.25)
4. **Amount plausibility** — checks if amount is reasonable for the stated purpose

**Example:**
```
Input:  "paying my daughter's MBA fees at a university in Dubai"
Output: { code: "P0103", label: "Remittances for studies abroad",
          confidence: "HIGH", score: 0.82,
          explanation: "Keywords 'university', 'fees' triggered match" }
```

**Why this matters to RBI:** Wrong FEMA codes trigger compliance reviews. This agent reduces errors at source before funds move.

---

### Sub-Agent 2: Transaction Risk Scoring Agent (`risk_agent.py`)

**What it does:** Scores every transfer 0–100 for fraud/compliance risk before execution.

**8 named rules (fully transparent):**

| Rule | Trigger | Points |
|------|---------|--------|
| `INVALID_ADDRESS` | Missing/malformed recipient | +15 |
| `ADDRESS_FORMAT` | Not valid Ethereum address | +10 |
| `LRS_LIMIT_EXCEEDED` | Amount > $250,000 equivalent | +30 |
| `LRS_LIMIT_APPROACHING` | Amount > $200,000 equivalent | +15 |
| `AMOUNT_EXCEEDS_PURPOSE_NORM` | 2x above typical for purpose | +15 |
| `HIGH_SCRUTINY_PURPOSE` | Business/professional codes | +8 |
| `HIGH_VELOCITY` | 3+ recent transfers | +12 |
| `CUMULATIVE_LRS_EXCEEDED` | History + this > LRS limit | +20 |

**Risk levels:**
- **LOW (0–20):** Approve automatically
- **MEDIUM (21–50):** Flag for review, allow with note
- **HIGH (51–100):** Block pending manual review

**Why this matters to RBI:** This is AI-native AML — every flag is auditable. The logic maps directly to RBI's risk-based supervision framework and FIU-IND reporting requirements.

---

### Sub-Agent 3: Regulatory Q&A Agent (`qa_agent.py`)

**What it does:** Answers questions about FEMA, LRS, e-Rupee, and RBI regulations.

**How it works:**
1. **TF-IDF retrieval** — finds the most relevant passages from 12 RBI knowledge chunks
2. **Answer generation:**
   - Without Groq key: returns retrieved passage with source citation
   - With Groq key (free tier): uses Llama 3.1 8B for natural language answer

**Knowledge base covers:**
- LRS annual limit and rules
- All FEMA purpose codes and requirements
- e-Rupee CBDC pilot details
- RBI Payments Vision 2025
- Regulatory Sandbox information
- AML/KYC requirements

**Optional Groq integration (free):**
```bash
# Get free key at: https://console.groq.com/keys
echo "GROQ_API_KEY=gsk_..." >> .env
```

---

## Project Structure

```
E-Rupee/
├── docs/
│   ├── index.html              # GitHub Pages showcase demo
│   └── ARCHITECTURE.md         # This document
│
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI — CBDC + agent endpoints
│   │   └── agent/
│   │       ├── __init__.py
│   │       ├── orchestrator.py # Routes to sub-agents
│   │       ├── fema_agent.py   # FEMA classification (TF-IDF + keywords)
│   │       ├── risk_agent.py   # Risk scoring (8 named rules)
│   │       ├── qa_agent.py     # Q&A (RAG + optional Groq)
│   │       └── knowledge_base.py # FEMA codes + RBI regulatory content
│   └── requirements.txt        # Zero extra deps for agent (stdlib only)
│
├── contracts/
│   ├── CBDCBridge.sol          # Bridge contract
│   └── MockStablecoin.sol      # Test ERC-20
│
├── scripts/deploy.js           # Hardhat → Sepolia
├── test/CBDCBridge.test.js     # Contract tests
└── tests/test_e2e.py           # API integration tests
```

---

## API Reference

### Core Transfer Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/v1/wallets/{id}` | Wallet balance |
| POST | `/v1/fx/quote` | FX rate + fee breakdown |
| POST | `/v1/erupee/transfer` | Execute transfer |
| GET | `/v1/transactions/{id}` | Transaction status |

### AI Agent Endpoints

| Method | Endpoint | Agent Used |
|--------|----------|-----------|
| GET | `/v1/agent/status` | All agents — health check |
| POST | `/v1/agent/classify-purpose` | FEMA Classification Agent |
| POST | `/v1/agent/score-risk` | Risk Scoring Agent |
| POST | `/v1/agent/ask` | Q&A Agent |
| POST | `/v1/agent/pre-check` | FEMA + Risk (combined) |

---

## Running Locally

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs
# → http://localhost:8000/v1/agent/status
```

**Test the agent directly:**
```bash
# FEMA classification
curl -X POST http://localhost:8000/v1/agent/classify-purpose \
  -H "Content-Type: application/json" \
  -d '{"description": "paying university fees in Dubai", "amount_inr": 500000}'

# Risk scoring
curl -X POST http://localhost:8000/v1/agent/score-risk \
  -H "Content-Type: application/json" \
  -d '{"sender_wallet": "INDIA_USER_001", "recipient_address": "0xAbCdEf1234567890abcdef1234567890AbCdEf12", "amount_inr": 10000, "purpose_code": "P0103", "recipient_country": "UAE"}'

# Ask a question
curl -X POST http://localhost:8000/v1/agent/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the LRS annual limit?", "session_id": "user-001"}'
```

---

## Production Enhancements

| Component | PoC (now) | Production |
|-----------|-----------|------------|
| FEMA agent | TF-IDF + keywords | Fine-tuned BERT on 10K RBI examples |
| Risk agent | 8 rule-based rules | + ML anomaly detection (Isolation Forest) |
| Q&A agent | RAG retrieval | + live RBI circular feed via scraper |
| Knowledge base | 12 static chunks | + auto-updated from rbi.org.in |
| e-Rupee API | Mock FastAPI | RBI e₹ Developer Sandbox |
| Settlement | Sepolia testnet | Permissioned DLT (Corda/Fabric) |
| Groq (optional) | Llama 3.1 8B | Self-hosted Llama on RBI-compliant infra |

---

## Contact & Submission

- GitHub: github.com/Abhishekveda/E-Rupee
- Live Demo: abhishekveda.github.io/E-Rupee
- RBIH Showcase: rbih.org.in · **Deadline: June 5, 2026**
- RBI FinTech Repository: fintech.rbi.org.in

*Not affiliated with RBI or RBIH. PoC only.*
