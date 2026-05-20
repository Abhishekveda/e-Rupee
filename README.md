# e₹ Bridge — AI-Powered CBDC Cross-Border Payment Bridge

**RBIH Bank-Fintech Showcase 2026** · Abhishek Veda · Toronto, Canada 🇨🇦

🌐 **Live Demo:** https://abhishekveda.github.io/E-Rupee  
📖 **Architecture:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## What's new in v2.0 — AI Layer

Version 2.0 adds Claude AI directly into the payment compliance workflow:

| AI Feature | What it does | Why it matters |
|------------|-------------|----------------|
| **FEMA Code Intelligence** | User types plain English → Claude selects correct FEMA code | Eliminates compliance errors at source |
| **Pre-Transfer Risk Engine** | Claude scores fraud risk before every transfer | AI-native AML — not bolt-on rule engine |
| **Regulatory Q&A** | Conversational assistant for LRS, FEMA, remittance rules | Reduces compliance burden for diaspora users |

---

## The Problem

India receives **$100B+ in remittances annually**. The average SWIFT fee is **6.3%** — $6.3 billion lost every year. Settlement takes 2–3 business days.

India's e-Rupee CBDC is already live with **60 lakh users across 17 banks**. This PoC shows how to build cross-border settlement on top of it.

## The Numbers

| | SWIFT | Wise | **e₹ Bridge** |
|-|-------|------|--------------|
| Fee | 6.3% | 2.1% | **0.2%** |
| Speed | 2–3 days | ~1 day | **< 3 seconds** |
| AI compliance | None | Basic | **Claude AI** |
| Cost on ₹10,000 | ₹630 | ₹210 | **₹20** |

---

## Architecture

```
🇮🇳 e-Rupee Wallet → ✦ Claude AI → ⛓ CBDC Bridge → Ethereum Contract → 🇦🇪 Recipient
   (RBI e₹-R)         (Compliance)    (FastAPI)        (CBDCBridge.sol)    (AED/SGD)
```

**Full docs:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Quick Start

```bash
# Backend (mock e-Rupee API + AI)
cd backend
pip install -r requirements.txt
echo "ANTHROPIC_API_KEY=your_key" > .env
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs

# Smart contracts
npm install && npx hardhat test

# Demo (no backend needed)
open docs/index.html
```

---

## Regulatory Alignment

- **Payments Vision 2025** — implements RBI's stated CBDC cross-border goal
- **e₹ Wholesale Pilot** — mirrors NDS-OM settlement architecture
- **Project Dunbar / mBridge** — open-source equivalent of BIS CBDC bridge
- **FEMA Compliance** — mandatory purpose codes + LRS cap enforcement
- **AI AML** — Claude risk engine with FIU-IND integration pathway

---

## Submission

- **RBIH Showcase:** https://rbih.org.in · **Deadline: June 5, 2026**
- **RBI FinTech Repository:** https://fintech.rbi.org.in
- **Contact:** github.com/Abhishekveda

---

*Not affiliated with RBI, RBIH, or Anthropic. PoC only — not for production use.*
