# e₹ Bridge — Cross-Border CBDC Payment Bridge

**RBIH Bank-Fintech Showcase 2026** · Submission by Abhishek Veda · Toronto, Canada

🌐 **Live Demo:** https://abhishekveda.github.io/E-Rupee

---

## The Problem

India receives **$100B+ in remittances annually** — the largest in the world. Yet:
- Average SWIFT fee: **6.3%** (World Bank 2024)
- Average settlement time: **2–3 business days**
- Total lost to fees: **~$6.3 billion every year**

India's e-Rupee CBDC infrastructure is already live with **60 lakh users across 17 banks**. This PoC demonstrates how it can power a cross-border settlement layer that eliminates correspondent banks entirely.

## The Solution

A CBDC-native bridge that:
- Debits the sender's **e-Rupee retail wallet** (RBI e₹-R)
- Relays a settlement hash to a **Solidity bridge contract** on Ethereum
- Converts via **FX oracle** and credits the recipient in AED or SGD
- Settles in **under 3 seconds** at **0.2% fee**

## Why it matters

| Method | Fee | Time |
|--------|-----|------|
| SWIFT / Bank wire | 6.3% | 2–3 days |
| Wise / Remitly | 2.1% | ~1 day |
| **e₹ Bridge (this PoC)** | **0.2%** | **< 3 seconds** |

## Architecture

```
🇮🇳 e-Rupee Wallet  →  ⛓ CBDC Bridge API  →  Ethereum Contract  →  🇦🇪 Recipient
   (RBI e₹-R)          (FastAPI + Solidity)    (CBDCBridge.sol)      (AED / SGD)
```

## RBI Policy Alignment

- **Payments Vision 2025** — implements RBI's stated cross-border CBDC settlement goal
- **e₹ Wholesale Pilot** — mirrors the e₹-W interbank settlement architecture  
- **Project Dunbar / mBridge** — open-source equivalent of BIS CBDC bridge concept
- **FEMA Compliance** — mandatory purpose codes on every transfer (P0102, P0103, P1301, P0801)
- **LRS Enforcement** — API architecture supports $250,000 annual cap per sender

## Project Structure

```
E-Rupee/
├── docs/               ← GitHub Pages live demo (index.html)
├── backend/app/        ← FastAPI mock e-Rupee CBDC API
├── contracts/          ← Solidity bridge contracts
│   ├── CBDCBridge.sol
│   └── MockStablecoin.sol
├── scripts/            ← Hardhat deployment
├── test/               ← Contract test suite
├── tests/              ← Python API integration tests
├── .github/workflows/  ← CI/CD (secret scan, tests, Slither)
└── SECURITY.md         ← Responsible disclosure policy
```

## Run Locally

### Backend API
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# Open: http://localhost:8000/docs
```

### Smart Contracts
```bash
npm install
npx hardhat compile
npx hardhat test

# Deploy to Sepolia
cp .env.example .env  # add your keys
npx hardhat run scripts/deploy.js --network sepolia
```

### Tests
```bash
# Start API first, then:
pytest tests/test_e2e.py -v
```

## What's Production-Ready vs PoC

| Component | PoC (current) | Production |
|-----------|---------------|------------|
| CBDC API | Mock FastAPI | RBI e₹ Developer Sandbox |
| Settlement | Sepolia testnet | Permissioned DLT (Corda) |
| FX rate | Hardcoded | Chainlink oracle |
| Stablecoin | Mock ERC-20 | CBUAE digital dirham |
| Relayer key | EOA wallet | HSM multi-sig |
| KYC | Not implemented | CERSAI / VKYC integration |

## Submission Details

- **Showcase:** RBIH Bank-Fintech Showcase 2026
- **Deadline:** June 5, 2026
- **Apply:** https://rbih.org.in
- **FinTech Repository:** https://rbi.org.in/Scripts/FinTechRepository.aspx
- **Contact:** github.com/Abhishekveda

---

*Not affiliated with RBI or RBIH. e-Rupee APIs simulated for demonstration purposes. All demo transfers are fictitious.*
