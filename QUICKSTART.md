# How to run e₹ Bridge — Step by Step

Complete guide. Every command tested. Zero assumptions.

---

## Prerequisites

You need:
- Python 3.10 or higher
- Node.js 18 or higher (for smart contracts only)
- Git
- A terminal (Windows: use Anaconda Prompt or PowerShell)

Check your versions:
```bash
python3 --version    # needs 3.10+
node --version       # needs 18+
git --version
```

---

## Step 1 — Clone the repository

```bash
git clone https://github.com/Abhishekveda/E-Rupee.git
cd E-Rupee
```

---

## Step 2 — Install Python dependencies

```bash
cd backend
pip install -r requirements.txt
```

If you're on Windows with Anaconda:
```bash
cd backend
& "C:\Users\YOUR_NAME\Anaconda3\python.exe" -m pip install -r requirements.txt
```

The requirements install: FastAPI, SQLAlchemy, python-jose, passlib, uvicorn, httpx.
The AI agents need zero extra packages — they use Python standard library only.

---

## Step 3 — Run the live POC demonstration

This runs all 5 AI agents and shows everything working:

```bash
# From the backend/ directory
python3 poc_demo.py
```

On Windows with Anaconda:
```bash
& "C:\Users\YOUR_NAME\Anaconda3\python.exe" poc_demo.py
```

**What you will see:**
```
Step 1 — Database initialisation
  ✓  SQLite database created: erupee_bridge.db

Step 2 — AI Agent system startup
  ✓  Orchestrator ready in 7ms
  ✓  Agent 'fema_agent' — ready
  ✓  Agent 'risk_agent' — ready
  ✓  Agent 'qa_agent' — ready
  ✓  Agent 'customer_agent' — ready
  ✓  Agent 'speed_agent' — ready

Step 3 — FEMA Classification Agent
  Input: "paying my daughter's MBA fees at a university in Dubai"
  → P0103 — Remittances for studies abroad  (HIGH confidence)

Step 4 — Risk Scoring Agent
  LRS limit breach → HIGH (79/100) → BLOCK

... and so on through 8 steps
```

---

## Step 4 — Start the API server

```bash
# From the backend/ directory
uvicorn app.main:app --reload --port 8000
```

Then open your browser at:
```
http://localhost:8000/docs
```

You will see the full interactive API documentation. Every endpoint has a "Try it out" button.

---

## Step 5 — Test the AI agents via API

Open a second terminal and run these curl commands:

**Check all agents are active:**
```bash
curl http://localhost:8000/v1/agent/status
```

**Classify a FEMA purpose code:**
```bash
curl -X POST http://localhost:8000/v1/agent/classify-purpose \
  -H "Content-Type: application/json" \
  -d '{"description": "paying university fees in Dubai", "amount_inr": 500000}'
```

**Score a transfer for risk:**
```bash
curl -X POST http://localhost:8000/v1/agent/score-risk \
  -H "Content-Type: application/json" \
  -d '{
    "sender_wallet": "INDIA_USER_001",
    "recipient_address": "0xAbCdEf1234567890abcdef1234567890AbCdEf12",
    "amount_inr": 10000,
    "purpose_code": "P0102",
    "recipient_country": "UAE"
  }'
```

**Ask a regulatory question:**
```bash
curl -X POST http://localhost:8000/v1/agent/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the LRS annual limit?", "session_id": "demo-001"}'
```

**Execute a full transfer:**
```bash
curl -X POST http://localhost:8000/v1/erupee/transfer \
  -H "Content-Type: application/json" \
  -d '{
    "sender_wallet": "INDIA_USER_001",
    "recipient_address": "0xAbCdEf1234567890abcdef1234567890AbCdEf12",
    "recipient_country": "UAE",
    "amount_inr": 10000,
    "purpose_code": "P0102"
  }'
```

**Get an INR bridge currency quote (USD → INR → AED):**
```bash
curl -X POST http://localhost:8000/v1/bridge/multi-hop-quote \
  -H "Content-Type: application/json" \
  -d '{
    "sender_country": "CA",
    "sender_currency": "CAD",
    "sender_amount": 200.0,
    "recipient_country": "UAE",
    "recipient_currency": "AED",
    "recipient_address": "0xAbCdEf1234567890abcdef1234567890AbCdEf12",
    "purpose_code": "P0102"
  }'
```

---

## Step 6 — View the live demo (no server needed)

Open this file directly in any browser:
```
docs/index.html
```

No server, no internet, no setup. Works completely offline.

---

## Step 7 — Run the smart contract tests (optional)

```bash
# From the root E-Rupee/ directory
npm install
npx hardhat compile
npx hardhat test
```

---

## Step 8 — Deploy contracts to Sepolia testnet (optional)

Create a `.env` file in the root directory:
```
PRIVATE_KEY=your_wallet_private_key
SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/your_project_id
```

Then:
```bash
npx hardhat run scripts/deploy.js --network sepolia
```

---

## Common errors and fixes

**`ModuleNotFoundError: No module named 'app'`**  
Make sure you are running from the `backend/` directory, not the root.

**`Address already in use` on port 8000**  
Another process is using port 8000. Use a different port:
```bash
uvicorn app.main:app --reload --port 8001
```

**`pip: command not found`**  
Use `pip3` instead of `pip`, or use your Anaconda Python path explicitly.

**`No module named 'sqlalchemy'`**  
You skipped Step 2. Run `pip install -r requirements.txt` from the `backend/` directory.

---

## Environment variables (optional)

Create a `.env` file in the `backend/` directory for optional features:

```
# Optional: enables Groq LLM for enhanced Q&A responses
# Free key at: https://console.groq.com/keys
GROQ_API_KEY=gsk_your_key_here

# Optional: PostgreSQL for production (default is SQLite)
DATABASE_URL=postgresql://user:password@localhost/erupee

# Optional: JWT secret (change before any real deployment)
JWT_SECRET_KEY=change-this-in-production

# When RBI Developer Sandbox opens:
CBDC_ENGINE=rbi
RBI_API_URL=https://sandbox.rbi.org.in/cbdc/v1
RBI_API_KEY=your_rbi_sandbox_key
```

---

## What each file does

| File | What it is |
|------|-----------|
| `backend/poc_demo.py` | Run this to see everything working live |
| `backend/app/main.py` | The API — all endpoints in one file |
| `backend/app/agent/fema_agent.py` | FEMA classification logic |
| `backend/app/agent/risk_agent.py` | Risk scoring rules |
| `backend/app/agent/qa_agent.py` | Q&A retrieval |
| `backend/app/database.py` | Database schema |
| `contracts/OCBPCore.sol` | The main smart contract |
| `docs/index.html` | Live demo — open in browser |
| `docs/showcase.html` | Presentation — open in browser |
| `RBI_SANDBOX_APPLICATION.md` | The formal RBI submission document |
| `HOW_TO_APPLY.md` | Every application pathway with URLs |

