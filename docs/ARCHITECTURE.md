# e₹ Bridge — Technical Architecture

**Version 2.0** · RBIH Bank-Fintech Showcase 2026 · Abhishek Veda, Toronto

---

## Overview

e₹ Bridge is a cross-border payment proof-of-concept built on India's e-Rupee CBDC. It shows how the RBI's retail CBDC pilot can be extended into international remittance corridors — reducing fees from 6.3% (SWIFT average) to 0.2%, and settlement time from 2–3 business days to under 3 seconds.

Version 2.0 adds a custom AI agent that handles compliance intelligence, fraud risk scoring, and regulatory Q&A — entirely in Python, with no third-party AI dependency.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — Sender                                                   │
│  Indian resident / NRI with e-Rupee retail wallet (e₹-R)           │
│  In PoC: simulated by FastAPI. In production: live RBI API         │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 2 — e₹ AI Agent  (pure Python · no external API)            │
│                                                                     │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────────────────┐│
│  │ FEMA Agent  │  │   Risk Agent     │  │      Q&A Agent         ││
│  │             │  │                  │  │                        ││
│  │ TF-IDF +    │  │ 8 named rules    │  │ RAG over 12 RBI        ││
│  │ keyword     │  │ score 0–100      │  │ knowledge chunks       ││
│  │ classifier  │  │ APPROVE/REVIEW/  │  │ optional Groq free     ││
│  │ 13 codes    │  │ BLOCK            │  │ tier for generation    ││
│  └─────────────┘  └──────────────────┘  └────────────────────────┘│
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 3 — CBDC Bridge (FastAPI)                                    │
│  e-Rupee wallet debit → CBDC hash → FX conversion → bridge relay   │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — Settlement (Ethereum Sepolia)                            │
│  CBDCBridge.sol releases mAED / mSGD tokens to recipient           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The AI Agent — Three Sub-Agents

### 1. FEMA Classification Agent

Most users sending remittances abroad have no idea what FEMA purpose codes are. Selecting the wrong one triggers RBI compliance reviews that delay transfers for days. This agent classifies the user's plain-English description into the correct code before any money moves.

**How it works:**

*Step 1 — keyword matching.* Each of the 13 FEMA codes in the knowledge base has an associated keyword list. The agent checks whether the user's description contains any of those keywords. If a strong match exists (confidence above 0.5), the result is returned immediately. This handles most common cases — "university fees", "medical treatment", "family support" — in well under a millisecond.

*Step 2 — TF-IDF cosine similarity.* For descriptions that don't trigger a keyword match, the agent builds a TF-IDF vector and computes cosine similarity against all 13 code vectors. This catches paraphrases: "paying for my son's operation in Dubai" does not contain the word "medical" but scores highly against P0801 because the surrounding terms share document-level weights.

The two scores are blended, and the response includes the code, a confidence label (HIGH / MEDIUM / LOW), the triggering keywords, a plain-English explanation, and an LRS note if the amount is relevant.

**Why this matters to RBI:** Compliance errors at source are a primary cause of remittance delays and false AML alerts. Getting the purpose code right before funds move reduces the downstream compliance burden at Authorised Dealer banks.

---

### 2. Transaction Risk Scoring Agent

The Risk Agent scores every transfer from 0 to 100 before it executes. Every flag has a named reason — there are no black-box scores that cannot be explained to an auditor.

**The eight rules:**

| Rule | Trigger | Score added |
|------|---------|-------------|
| `INVALID_ADDRESS` | Recipient address missing or malformed | 15 |
| `ADDRESS_FORMAT` | Not a valid Ethereum address | 10 |
| `LRS_LIMIT_EXCEEDED` | Amount exceeds $250,000 equivalent | 30 |
| `LRS_LIMIT_APPROACHING` | Amount exceeds $200,000 equivalent | 15 |
| `AMOUNT_EXCEEDS_PURPOSE_NORM` | More than 2× the typical range for the stated purpose | 15 |
| `HIGH_SCRUTINY_PURPOSE` | Business or professional service purpose codes | 8 |
| `HIGH_VELOCITY` | Three or more recent transfers from this wallet | 12 |
| `CUMULATIVE_LRS_EXCEEDED` | History plus this transfer exceeds the LRS annual limit | 20 |

Scores 0–20 are approved automatically. 21–50 are flagged for review but not blocked. Above 50 are blocked pending manual clearance.

**Why this matters to RBI:** The rule set maps directly to the red flag indicators in RBI's KYC Master Direction and the suspicious transaction reporting thresholds for FIU-IND. An auditor can read the code, understand every decision, and update rules as regulations change without any model retraining.

---

### 3. Regulatory Q&A Agent

The Q&A Agent answers questions about FEMA codes, LRS limits, the e-Rupee CBDC, and RBI regulations in plain English, with citations to source documents.

**How it works:**

The knowledge base contains 12 hand-curated chunks drawn from RBI Master Directions, FEMA Rules, the e-Rupee Concept Note, and Payments Vision 2025. When a question arrives, the agent retrieves the most relevant chunks using TF-IDF cosine similarity and returns the passage alongside its source.

Installations with a Groq API key configured (free tier at console.groq.com/keys) additionally pass the retrieved context to Llama 3.1 8B for natural language generation. Without the key, the retrieval-only mode is accurate and fully functional.

---

## Repository Layout

```
E-Rupee/
├── docs/
│   ├── index.html            Self-contained live demo (no backend required)
│   └── ARCHITECTURE.md       This document
├── backend/
│   ├── app/
│   │   ├── main.py           API layer — CBDC simulation and agent routing
│   │   └── agent/
│   │       ├── orchestrator.py   Central router and session manager
│   │       ├── fema_agent.py     FEMA classification
│   │       ├── risk_agent.py     Risk scoring
│   │       ├── qa_agent.py       Regulatory Q&A
│   │       └── knowledge_base.py FEMA codes and RBI regulatory content
│   └── requirements.txt      FastAPI stack — no AI library dependency
├── contracts/
│   ├── CBDCBridge.sol         Bridge contract
│   └── MockStablecoin.sol     Test ERC-20 (mAED, mSGD)
├── scripts/deploy.js         Hardhat deployment to Sepolia
├── test/CBDCBridge.test.js   Contract test suite
├── tests/test_e2e.py         API integration tests
└── .github/workflows/        CI/CD — secret scan, lint, Slither, deploy
```

---

## API Reference

### Transfer endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/v1/wallets/{id}` | Wallet balance |
| `POST` | `/v1/fx/quote` | FX rate and fee breakdown |
| `POST` | `/v1/erupee/transfer` | Execute a transfer |
| `GET` | `/v1/transactions/{id}` | Transaction status |

### Agent endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/agent/status` | Agent readiness and capabilities |
| `POST` | `/v1/agent/classify-purpose` | FEMA code from plain English |
| `POST` | `/v1/agent/score-risk` | Risk score for a pending transfer |
| `POST` | `/v1/agent/ask` | Regulatory Q&A |
| `POST` | `/v1/agent/pre-check` | Combined FEMA and risk pre-flight |

---

## Running Locally

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# Interactive docs: http://localhost:8000/docs
# Agent status:    http://localhost:8000/v1/agent/status

# Optional Groq integration (free tier)
echo "GROQ_API_KEY=gsk_your_key_here" >> .env
```

The demo at `docs/index.html` works without any running server.

---

## From PoC to Production

| Component | Now (PoC) | Production path |
|-----------|-----------|-----------------|
| e-Rupee API | Mock simulation | RBI e₹ developer sandbox |
| FX rate | Hardcoded | Chainlink INR/AED price feed |
| Settlement token | Mock ERC-20 | CBUAE digital dirham |
| Settlement network | Ethereum Sepolia | RBI-specified permissioned DLT |
| Relayer key | Development wallet | HSM-backed multi-signature |
| FEMA agent | TF-IDF, 13 codes | Fine-tuned on full 400+ code corpus |
| Risk agent | 8 static rules | Rules + ML anomaly detection |
| Knowledge base | 12 static chunks | Live feed from rbi.org.in |
| KYC | Not implemented | CERSAI / V-CIP |

---

## Regulatory Alignment

| RBI Policy | Implementation |
|------------|----------------|
| Payments Vision 2025 | Directly implements the stated CBDC cross-border settlement objective |
| e-Rupee Wholesale Pilot | Bridge relay mirrors the NDS-OM mechanism used in the e₹-W pilot |
| Project Dunbar / mBridge | Open-source equivalent of the BIS CBDC-to-CBDC bridge concept |
| FEMA Master Direction | Mandatory purpose codes; AI agent reduces code errors at source |
| LRS Rules | Architecture enforces the $250,000 annual limit; agent flags proximity |
| KYC Master Direction | Risk agent rules map to RBI's AML red flag indicators |
| Regulatory Sandbox | Designed for RBI Regulatory Sandbox entry — cross-border CBDC category |

---

*Proof of concept. Not affiliated with RBI, RBIH, or any bank. e-Rupee APIs are simulated.*
