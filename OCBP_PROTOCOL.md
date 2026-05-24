# Open CBDC Bridge Protocol (OCBP)
## Technical Specification v1.0

**Author:** Abhishek Veda · e₹ Bridge  
**Status:** Draft — submitted to RBIH Bank-Fintech Showcase 2026  
**Target:** RBI Regulatory Sandbox · BRICS CBDC Summit 2026

---

## Why India Can Win Where China Cannot

China's digital yuan (e-CNY) is deployed at scale — 260 million wallets, $250 billion in transactions. But it has a structural weakness that no engineering can fix: **trust**. Every transaction is visible to the People's Bank of China. No country wants to replace dollar dependency with Chinese surveillance dependency.

India can build something structurally different. A CBDC bridge where:
- Compliance is **provable without being visible**
- No single country can **surveil** another's transactions
- No single country can **freeze** another's funds
- The protocol is **open** — any nation can implement it

That is OCBP. India leads it. The world adopts it. The INR becomes the neutral global settlement currency — not because India forced it, but because every country trusts it.

---

## Protocol Architecture

### Layer 0 — Identity (Private KYC)

Every participant in the protocol has a **cryptographic identity** that proves they are KYC-verified without revealing who they are to foreign parties.

```
User → Indian Bank → KYC commitment = H(PAN, Aadhaar, nonce)
                   → Posted on-chain
                   → Verifiable by any OCBP participant
                   → Reveals nothing about the user's identity
```

In production: uses a ZK-SNARK circuit that proves "this wallet belongs to a KYC-verified Indian resident" without revealing the PAN or Aadhaar.

### Layer 1 — Compliance (Private FEMA)

Before any transfer, the AI compliance agent generates a **commitment** to the compliance metadata:

```
commitment = H(fema_category || lrs_amount || risk_score || nonce || address)
```

This commitment is posted on-chain. The actual FEMA code, LRS amount, and risk score stay off-chain. The RBI can verify compliance by asking the user to reveal the preimage — foreign regulators never see it.

**This is the key innovation.** China's e-CNY posts transaction details on-chain and China sees them. OCBP posts only a commitment — compliance is proven, details are private.

### Layer 2 — Settlement (Atomic Cross-Chain)

```
Step 1: India side — lock e-Rupee in OCBP escrow
Step 2: Destination side — lock destination CBDC in corresponding escrow  
Step 3: Both sides confirm readiness (2-of-2 or 2-of-3 multi-sig)
Step 4: Atomic release — both sides settle simultaneously
Step 5: If either fails — both refund automatically after timeout
```

No correspondent bank. No nostro/vostro account. No USD intermediary.

### Layer 3 — Audit (Transparent to Regulators, Private to Users)

Every settlement emits an on-chain event containing:
- Transfer ID
- Compliance commitment hash
- AI risk score
- FEMA category (not the full code)
- Settlement timestamp

RBI and FIU-IND can audit the entire history. They can see **that** every transaction was compliant. They cannot see **what** it was for, **who** sent it, or **how much** — unless they request disclosure through the legal process.

---

## What the Team Needs to Build

### Sprint 1 (Months 1–3) — Foundations
- [ ] ZK-SNARK circuits in Circom (FEMA compliance proof, LRS limit proof)
- [ ] Groth16 prover integration (replaces hash commitment)
- [ ] HSM integration (AWS CloudHSM or Thales Luna)
- [ ] Production PostgreSQL schema with row-level encryption
- [ ] CERT-In security audit of smart contracts

### Sprint 2 (Months 4–6) — First Corridor
- [ ] UAE Digital Dirham API integration (CBUAE sandbox)
- [ ] RBI Developer Sandbox integration (when available)
- [ ] Chainlink FX oracle integration (live INR/AED rates)
- [ ] FIU-IND STR report generation
- [ ] End-to-end security penetration test

### Sprint 3 (Months 7–12) — BRICS Expansion
- [ ] Singapore MAS Project Orchid integration
- [ ] Brazil BCB DREX integration
- [ ] South Africa SARB CBDC integration
- [ ] BRICS interoperability summit demo (September 2026)
- [ ] Production deployment on AWS ap-south-1

### What to Build for China Corridor
The e-CNY corridor requires a bilateral agreement between RBI and PBOC. The technical architecture is identical — only the API adapter changes. The protocol does NOT give China surveillance over Indian transactions — that is the selling point. RBI can propose this at the BRICS summit: "We will connect to e-CNY if and only if the connection is privacy-preserving on both sides."

---

## Team You Need to Hire

### Core Engineering (4 people)
1. **ZK cryptographer** — Circom, snarkjs, Groth16, ZK proof generation
2. **Smart contract engineer** — Solidity, formal verification, Certora
3. **Backend engineer** — Python/FastAPI, PostgreSQL, distributed systems
4. **DevSecOps** — HSM integration, CERT-In audit, AWS GovCloud

### Regulatory (2 people)
5. **RBI compliance specialist** — PA-CB licence, Regulatory Sandbox application
6. **FEMA/PMLA counsel** — cross-border payment legal framework

### Business (2 people)
7. **Bank partnerships** — BD with SBI, HDFC, Axis for the first pilot
8. **BRICS partnerships** — RBI liaison, MEA contacts for bilateral CBDC agreements

### Total runway needed: ₹3–5 crore for 18 months to pilot

---

## The Ask

**At the RBIH Showcase:** Regulatory Sandbox slot + one bank pilot partner  
**At the BRICS Summit:** Present OCBP as India's contribution to BRICS CBDC interconnection  
**At MEA:** Bilateral CBDC agreement framework for UAE, Singapore, Russia  

The code is open source. Every bank, every central bank, every BRICS country can verify it, audit it, and trust it — because nobody controls it.

---

## Contact

**Abhishek Veda** · Toronto, Canada  
GitHub: github.com/Abhishekveda/E-Rupee  
RBIH Showcase deadline: June 5, 2026 · rbih.org.in
