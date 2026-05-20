# e₹ Bridge — Custom AI Agent + CBDC Cross-Border Payments

**RBIH Bank-Fintech Showcase 2026** · Abhishek Veda · Toronto, Canada 🇨🇦

🌐 **Live Demo:** https://abhishekveda.github.io/E-Rupee  
📖 **Architecture:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Custom AI Agent (v2.0) — No External API

Version 2.0 replaces any third-party AI dependency with a **fully custom AI agent** built in pure Python. Zero paid API calls. Runs 100% locally.

| Agent | Method | Purpose |
|-------|--------|---------|
| **FEMA Classification Agent** | TF-IDF + keyword matching | Plain English → correct FEMA code |
| **Risk Scoring Agent** | 8 named rule-based rules | Fraud/compliance score 0–100 |
| **Regulatory Q&A Agent** | RAG over RBI knowledge base | FEMA, LRS, e-Rupee questions |

**Why custom?**
- Fully explainable — every decision has a named rule
- RBI can audit the exact logic
- Zero external dependency — runs offline
- Trainable — add more RBI circulars to `knowledge_base.py`

---

## The Problem

India receives **$100B+ annually** in remittances — the world's largest. Average SWIFT fee: **6.3%**. Settlement: **2–3 days**. $6.3 billion lost to fees every year.

## The Numbers

| | SWIFT | Wise | **e₹ Bridge** |
|-|-------|------|--------------|
| Fee | 6.3% | 2.1% | **0.2%** |
| Speed | 2–3 days | ~1 day | **< 3 seconds** |
| AI compliance | None | Basic | **Custom Agent** |
| Cost on ₹10,000 | ₹630 | ₹210 | **₹20** |

---

## Architecture

```
Sender → e₹ AI Agent (FEMA + Risk + Q&A) → CBDC Bridge → Ethereum → Recipient
          (pure Python, no external API)     (FastAPI)     (Solidity)
```

Full docs: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Quick Start

```bash
cd backend
pip install -r requirements.txt          # zero extra deps for agent
uvicorn app.main:app --reload --port 8000

# Test the AI agent
curl -X POST localhost:8000/v1/agent/classify-purpose \
  -d '{"description": "university fees in Dubai", "amount_inr": 500000}'

curl -X GET localhost:8000/v1/agent/status

# Optional: Groq free-tier LLM for enhanced Q&A
# Get key at console.groq.com/keys
echo "GROQ_API_KEY=gsk_..." >> .env
```

---

## Regulatory Alignment

- **Payments Vision 2025** — implements RBI's CBDC cross-border settlement goal
- **e₹ Wholesale Pilot** — mirrors NDS-OM settlement architecture
- **FEMA Compliance** — mandatory purpose codes + LRS enforcement
- **AI AML** — transparent risk engine with FIU-IND integration pathway

---

**RBIH Showcase:** rbih.org.in · **Deadline: June 5, 2026**

*PoC only — not affiliated with RBI or RBIH.*
