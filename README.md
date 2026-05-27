# e₹ Bridge — AI-Native CBDC Cross-Border Payment Protocol

**RBIH Bank-Fintech Showcase 2026** · Abhishek Veda · Toronto, Canada

🌐 **Live demo:** https://abhishekveda.github.io/e-Rupee  
📋 **RBI Application:** [RBI_SANDBOX_APPLICATION.md](RBI_SANDBOX_APPLICATION.md)  
🏗️ **Architecture:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)  
🔐 **Protocol spec:** [OCBP_PROTOCOL.md](OCBP_PROTOCOL.md)

---

## What this is

An AI compliance and CBDC settlement protocol that:
- Reduces cross-border remittance fees from **6.3% → 0.2%**
- Reduces settlement time from **3 days → 3 seconds**
- Automates FEMA purpose code selection using a custom AI agent
- Uses the **INR as a bridge currency** — no USD required
- Gives every regulator a transparent, auditable compliance trail

The AI agent is custom-built. No external API. Runs entirely on your machine.

---

## Quick start — run it in 3 commands

```bash
git clone https://github.com/Abhishekveda/E-Rupee.git
cd E-Rupee/backend
pip install -r requirements.txt && python poc_demo.py
```

That runs all 5 AI agents, classifies FEMA codes, scores risk, answers regulatory questions, and writes a transaction to the database — all locally, zero external calls.

---

## Run the full API server

```bash
cd backend
uvicorn app.main:app --reload --port 8000
# Open: http://localhost:8000/docs
```

---

## Repository structure

```
E-Rupee/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI — all endpoints
│   │   ├── database.py          SQLite (PoC) / PostgreSQL schema
│   │   ├── auth.py              JWT authentication
│   │   ├── cbdc/engine.py       CBDC abstraction layer
│   │   ├── crypto/hsm.py        HSM key management
│   │   └── agent/
│   │       ├── orchestrator.py  Routes to all 5 sub-agents
│   │       ├── fema_agent.py    FEMA classification (TF-IDF)
│   │       ├── risk_agent.py    Risk scoring (8 named rules)
│   │       ├── qa_agent.py      Regulatory Q&A (RAG)
│   │       ├── customer_agent.py Customer service (8 intents)
│   │       ├── speed_agent.py   Route optimisation
│   │       └── knowledge_base.py FEMA codes + RBI circulars
│   ├── poc_demo.py              Live POC demonstration
│   └── requirements.txt
├── contracts/
│   ├── OCBPCore.sol             Main bridge protocol contract
│   ├── ZKCompliance.sol         Privacy-preserving compliance
│   ├── CBDCBridge.sol           Original bridge contract
│   └── MockStablecoin.sol       Test ERC-20 (mAED, mSGD)
├── docs/
│   ├── index.html               Live demo (GitHub Pages)
│   ├── showcase.html            Animated presentation
│   └── ARCHITECTURE.md          Technical documentation
├── RBI_SANDBOX_APPLICATION.md   Formal RBI submission
├── OCBP_PROTOCOL.md             Protocol specification
├── COMPLIANCE.md                PA-CB compliance checklist
└── INDIA_STRATEGY.md            INR internationalisation strategy
```

---

## The 5 AI agents

| Agent | Method | What it does |
|-------|--------|-------------|
| FEMA Classification | TF-IDF + keywords | Plain English → correct FEMA purpose code |
| Risk Scoring | 8 named rules | 0–100 score, every flag explained |
| Regulatory Q&A | RAG over RBI circulars | Answers LRS, FEMA, e-Rupee questions |
| Customer Service | 8 intent types | Transfer status, flags, LRS balance |
| Speed Optimiser | 12 corridors | CBDC direct vs SRVA vs multi-hop |

---

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/agent/status` | Agent health check |
| `POST` | `/v1/agent/classify-purpose` | FEMA code from plain English |
| `POST` | `/v1/agent/score-risk` | Risk score before transfer |
| `POST` | `/v1/agent/ask` | Regulatory Q&A |
| `POST` | `/v1/agent/pre-check` | Full compliance pre-flight |
| `POST` | `/v1/erupee/transfer` | Execute transfer |
| `POST` | `/v1/bridge/multi-hop-quote` | USD → INR → AED quote |

---

## Apply to RBI

See [HOW_TO_APPLY.md](HOW_TO_APPLY.md) — every submission pathway with exact URLs, email addresses, and what to write.

---

*Proof of concept. Not affiliated with RBI or RBIH. e-Rupee APIs simulated pending sandbox access.*
