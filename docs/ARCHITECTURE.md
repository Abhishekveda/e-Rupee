# e₹ Bridge — Complete Architecture & Documentation

**Version 2.0 — AI-Enhanced CBDC Cross-Border Payment Bridge**  
RBIH Bank-Fintech Showcase 2026

---

## What This Is

e₹ Bridge is a proof-of-concept cross-border payment system built on India's e-Rupee CBDC infrastructure. It demonstrates how the existing RBI e₹-R (retail) pilot can be extended to settle international remittances — eliminating correspondent banks, reducing fees from 6.3% (SWIFT) to 0.2%, and settling in under 3 seconds instead of 2–3 business days.

**Version 2.0 adds an AI intelligence layer** powered by Claude (Anthropic), making this the first CBDC bridge with embedded compliance AI.

---

## The Problem

India receives **$100 billion+ in remittances annually** — the world's largest recipient. Yet:

- Average SWIFT fee: **6.3%** (World Bank 2024)
- Average settlement time: **2–3 business days**
- Total lost to fees: **~$6.3 billion per year**
- Wrong FEMA codes trigger RBI compliance reviews, causing delays
- Users don't understand LRS limits until they breach them

---

## The Solution — Four Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 1: SENDER                                                     │
│  Indian diaspora user (Canada/UAE/SG) with e-Rupee retail wallet    │
│  RBI e₹-R pilot — 60 lakh users, 17 banks, live since Dec 2022     │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────────┐
│  LAYER 2: AI INTELLIGENCE (NEW in v2.0)                             │
│  Claude (Anthropic claude-sonnet-4-20250514)                        │
│  ├─ FEMA Code Intelligence: plain English → correct purpose code    │
│  ├─ Transaction Risk Engine: fraud score before transfer executes   │
│  └─ Market Q&A Assistant: regulatory guidance in plain language     │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────────┐
│  LAYER 3: CBDC BRIDGE (this PoC)                                    │
│  FastAPI backend simulating RBI e-Rupee API                         │
│  ├─ Wallet debit (CBDC lock)                                        │
│  ├─ FX oracle (Chainlink in production, hardcoded for PoC)          │
│  ├─ CBDC tx hash generation                                         │
│  └─ Ethereum bridge relay (CBDCBridge.sol on Sepolia)               │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────────┐
│  LAYER 4: DESTINATION                                               │
│  Recipient wallet receives mAED or mSGD (mock stablecoins)         │
│  In production: CBUAE digital dirham / MAS Digital SGD             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
E-Rupee/
│
├── docs/                          GitHub Pages live demo
│   ├── index.html                 Self-contained showcase UI (no backend needed)
│   └── ARCHITECTURE.md            This document
│
├── backend/                       FastAPI CBDC + AI backend
│   ├── app/
│   │   ├── main.py               API endpoints (CBDC + AI)
│   │   └── ai_service.py         Claude AI integration layer
│   └── requirements.txt          Python dependencies (includes anthropic SDK)
│
├── contracts/                     Solidity smart contracts
│   ├── CBDCBridge.sol            Main bridge contract
│   └── MockStablecoin.sol        Test ERC-20 (mAED / mSGD)
│
├── scripts/
│   └── deploy.js                 Hardhat deployment to Sepolia
│
├── test/
│   └── CBDCBridge.test.js        Contract test suite (Hardhat)
│
├── tests/
│   └── test_e2e.py               Python API integration tests
│
├── .github/workflows/
│   ├── ci.yml                    CI: secret scan + tests + Slither
│   └── deploy.yml                CD: manual-approval Sepolia deploy
│
├── SECURITY.md                   Responsible disclosure policy
├── README.md                     Showcase submission brief
└── ARCHITECTURE.md               This document
```

---

## AI Features — Deep Dive

### Feature 1: FEMA Code Intelligence

**The problem it solves:**  
Most users sending money abroad don't know FEMA purpose codes. Selecting the wrong code (e.g., P0102 Family Maintenance when the actual purpose is P0103 Education Fees) triggers RBI compliance reviews, delays transfers, and can result in tax implications.

**How it works:**  
1. User types their purpose in plain English: *"paying my daughter's MBA fees at a university in Dubai"*
2. `POST /v1/ai/suggest-purpose` sends this to Claude with a system prompt containing all valid FEMA codes and RBI guidance
3. Claude returns: `{"code": "P0103", "label": "Education fees paid abroad", "confidence": "HIGH", "explanation": "...", "lrs_note": "..."}`
4. The frontend auto-selects the correct dropdown option

**Why this matters for RBI:**  
Reduces FEMA compliance errors at source, improving data quality for the RBI's cross-border payment monitoring systems. In production, this integrates with the RBI's SWIFT gpi-equivalent data pipeline.

---

### Feature 2: Pre-Transfer Risk Analysis

**The problem it solves:**  
Cross-border payment fraud is the fastest-growing financial crime segment. Banks currently rely on rule-based systems that either miss sophisticated fraud or create too many false positives. AI can identify nuanced patterns that rules cannot.

**How it works:**  
1. Before a transfer executes, `POST /v1/ai/risk-analysis` is called
2. Claude receives: sender wallet ID, recipient address, amount, purpose code, destination country, sender's transfer history
3. Claude analyses: amount vs purpose consistency, velocity patterns, LRS proximity, recipient address validity, time-of-day signals
4. Returns: `{"risk_level": "LOW|MEDIUM|HIGH", "risk_score": 0-100, "recommendation": "APPROVE|REVIEW|BLOCK", "factors": [...], "compliance_checks": {...}}`

**In production, this would also connect to:**  
- CERSAI database (sanctioned entities list)
- FIU-IND (Financial Intelligence Unit — suspicious transaction reports)
- RBI's negative list for remittances
- Chainlink-verified identity oracle

**Why this matters for RBI:**  
This is the architecture for an AI-native compliance layer — the kind regulators globally are looking for as they move beyond rule-based AML to risk-based supervision.

---

### Feature 3: Conversational Market Intelligence

**The problem it solves:**  
Users making cross-border transfers have regulatory questions they can't easily answer: "How much have I sent this year?" "What does P0802 mean?" "Can I send money for this purpose?" Currently they have to read 40-page RBI circulars or call their bank.

**How it works:**  
1. `POST /v1/ai/chat` accepts a user message + session ID + optional current transfer context
2. Claude has a system prompt with: current FX rates, all FEMA codes, LRS rules, RBI cross-border payment framework
3. Conversation history is maintained per session (last 10 exchanges)
4. Responses are contextually aware of the user's current transfer

**Example exchanges:**  
- *"Is ₹15 lakh too much to send for family maintenance?"* → Claude explains LRS limit, suggests splitting across financial years if needed
- *"My transfer was flagged — what should I do?"* → Claude explains the review process and what documentation to prepare
- *"What's the difference between e₹-W and e₹-R?"* → Claude explains wholesale vs retail CBDC with practical implications

---

## API Reference

### Core Transfer Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check + feature list |
| GET | `/v1/wallets/{id}` | Get wallet balance |
| POST | `/v1/wallets/topup` | Add test funds |
| POST | `/v1/fx/quote` | Get FX rate + fee breakdown |
| POST | `/v1/erupee/transfer` | **Execute cross-border transfer** |
| GET | `/v1/transactions/{id}` | Get transaction status |
| GET | `/v1/transactions` | List transactions |

### AI Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/ai/suggest-purpose` | FEMA code from plain English |
| POST | `/v1/ai/risk-analysis` | Risk score before transfer |
| POST | `/v1/ai/chat` | Conversational Q&A |
| POST | `/v1/ai/transfer-summary` | Plain-English audit summary |

---

## Running Locally

### Prerequisites
- Python 3.11+
- Node.js 18+
- Anthropic API key (for AI features)

### Backend
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Set API key (for AI features)
cp .env.example .env
# Add: ANTHROPIC_API_KEY=your_key_here

# Start server
uvicorn app.main:app --reload --port 8000

# Open interactive docs
# http://localhost:8000/docs
```

### Smart Contracts
```bash
npm install
npx hardhat compile
npx hardhat test
npx hardhat run scripts/deploy.js --network sepolia  # needs .env
```

### Demo (no backend needed)
```
Open docs/index.html in any browser
Everything works without a running server
AI features run in demo mode (simulated responses)
```

---

## What's PoC vs Production

| Component | Current PoC | Production |
|-----------|-------------|------------|
| e-Rupee API | Mock FastAPI | RBI e₹ Developer Sandbox |
| AI model | claude-sonnet-4-20250514 | Same, or fine-tuned for RBI regulations |
| FX rate | Hardcoded constants | Chainlink INR/AED price feed |
| Stablecoin | MockStablecoin ERC-20 | CBUAE digital dirham / MAS Digital SGD |
| Settlement | Sepolia testnet | RBI-specified permissioned DLT (Corda/Fabric) |
| Relayer key | Development EOA | HSM-backed multi-sig (Gnosis Safe) |
| KYC | Not implemented | CERSAI / VKYC integration |
| AI data | System prompt only | Live RBI regulation feed + CERSAI integration |
| Risk model | Claude zero-shot | Claude fine-tuned on RBI suspicious transaction patterns |

---

## Regulatory Alignment

| RBI Policy | How e₹ Bridge Implements It |
|------------|---------------------------|
| Payments Vision 2025 | Cross-border CBDC settlement — directly stated goal |
| e₹ Wholesale Pilot | Bridge relay mirrors NDS-OM settlement mechanism |
| Project Dunbar / mBridge | Open-source CBDC-to-CBDC bridge concept |
| FEMA compliance | Mandatory purpose code on every transfer |
| LRS enforcement | API architecture supports $250,000 annual cap |
| AML/CFT | AI risk engine + FIU-IND integration pathway |

---

## Security

See `SECURITY.md` for responsible disclosure policy.

**Key security notes for PoC:**
- Never commit `.env` (blocked by `.gitignore`)
- `deployed-addresses.json` is gitignored (contains live contract addresses)
- CI pipeline runs TruffleHog secret scanning on every push
- Slither static analysis on every Solidity change
- Deploy workflow has manual approval gate

---

## Contact & Submission

- **GitHub:** github.com/Abhishekveda/E-Rupee
- **Live Demo:** abhishekveda.github.io/E-Rupee
- **RBIH Showcase:** rbihub.in
- **RBI FinTech Repository:** fintech.rbi.org.in
- **Deadline:** June 5, 2026

---

*Not affiliated with RBI, RBIH, or Anthropic. e-Rupee APIs simulated. All demo transfers fictitious.*
