# Application for Regulatory Sandbox — Cross-Border Payments
## Reserve Bank of India · Cohort 2 (On Tap)

**Applicant:** Abhishek Veda  
**Entity:** e₹ Bridge Technologies (proposed — incorporation pending)  
**Date:** May 2026  
**Reference Framework:** RBI Enabling Framework for Regulatory Sandbox (August 13, 2019)  
**Contact:** [To be updated with India entity address]  
**GitHub:** github.com/Abhishekveda/E-Rupee

---

## Section 1 — Executive Summary

e₹ Bridge is an AI-native cross-border payment protocol built on India's e-Rupee CBDC infrastructure. It reduces remittance fees from 6.3% (SWIFT average) to 0.2%, eliminates settlement delays from 2–3 business days to under 3 seconds, and uses the Indian Rupee as the settlement currency — removing the US Dollar as an intermediary for India-to-Gulf and India-to-ASEAN payments.

The protocol introduces three capabilities that do not exist in any current cross-border payment system in India:

1. **Programmable compliance** — an AI agent classifies FEMA purpose codes automatically from plain-English descriptions, reducing compliance errors at source and eliminating the manual AD bank intervention currently required for purpose code verification.

2. **Privacy-preserving compliance attestation** — a cryptographic commitment scheme allows regulators to verify that every transfer is FEMA-compliant and within LRS limits, without any sensitive user information appearing on-chain. This is architecturally distinct from China's e-CNY, where transaction details are visible to the issuing central bank.

3. **INR as bridge currency** — the protocol routes third-country payments through the Indian Rupee (USD → INR → AED), creating demand for INR globally and positioning India as a neutral payment hub for BRICS and Gulf trade.

**What we are asking for:** A Regulatory Sandbox slot under Cohort 2 (Cross-Border Payments) to test the protocol with real e-Rupee wallets, a participating Authorised Dealer bank, and a minimum viable set of real users in the India-UAE corridor.

---

## Section 2 — Problem Statement

### 2.1 The fee problem

India is the world's largest recipient of remittances, receiving over $100 billion annually. The average cost of sending money to India via SWIFT is 6.3% (World Bank Remittance Prices Worldwide, Q4 2024). This means approximately $6.3 billion — money belonging to Indian workers and their families — is lost to correspondent bank fees every year.

The UN Sustainable Development Goal target is 3% by 2030. The global average has not moved meaningfully in a decade. Rule-based fintech solutions (Wise, Remitly) have reduced fees to approximately 2.1%, but remain dependent on the same correspondent banking rails.

### 2.2 The CBDC gap

The Reserve Bank launched the e-Rupee retail pilot in December 2022. As of March 2025, over 60 lakh users across 17 banks are participating. The infrastructure exists. What does not exist is a developer-accessible layer that extends the e-Rupee into cross-border settlement.

RBI Deputy Governor T. Rabi Sankar stated at Global Fintech Fest 2025: *"The basic use case for CBDC eventually comes in the cross-border space. We have to get into a few cross-border arrangements."* The SRVA (Special Rupee Vostro Account) framework is already signed with UAE, Malaysia, Maldives, and 17 other countries. The policy infrastructure exists. The technology layer does not.

### 2.3 The compliance burden

Currently, every outward remittance processed by an Authorised Dealer bank requires:
- Manual selection of FEMA purpose code by the remitter
- Manual LRS usage tracking
- Manual suspicious transaction identification
- Manual reporting to FIU-IND above thresholds

A significant proportion of FEMA errors occur at the purpose code selection stage. Wrong codes trigger compliance reviews, delay settlements, and create unnecessary documentation burden for both the remitter and the AD bank. There is no automated solution to this problem in the Indian market.

---

## Section 3 — Proposed Solution

### 3.1 Protocol overview

e₹ Bridge is implemented as a four-layer protocol:

**Layer 1 — Identity**  
Users are identified by their e-Rupee wallet ID, which is already KYC-verified through the participating bank. No additional KYC burden is created. The wallet ID serves as the identity anchor for LRS tracking across transfers.

**Layer 2 — Compliance (AI Agent)**  
Before any transfer is executed, five AI sub-agents run in sequence:
- FEMA Classification Agent: maps plain-English purpose to the correct FEMA code using TF-IDF cosine similarity across the full code set
- Risk Scoring Agent: scores 0–100 using eight named, transparent rules mapped to RBI's KYC Master Direction
- LRS Calculator: checks remaining annual LRS quota for the wallet
- Regulatory Q&A Agent: answers user questions about FEMA, LRS, and RBI regulations using RAG over 12 RBI regulatory chunks
- Speed Optimisation Agent: recommends the fastest compliant corridor (CBDC direct, SRVA, multi-hop)

None of these agents use an external API. All logic runs locally. RBI can audit every decision.

**Layer 3 — Settlement**  
The core settlement contract (OCBPCore.sol) implements:
- Compliance commitment scheme: a cryptographic hash of the FEMA code, LRS amount, and risk score is posted on-chain; the actual values remain off-chain
- Atomic settlement: funds lock on both sides simultaneously; either both complete or both refund
- Multi-signature for high-value transfers: transfers above ₹1 crore require 2-of-3 signatures from sending bank, receiving bank, and bridge operator
- PA-CB transaction limit: hard-enforced at ₹25 lakh per the RBI Payment Aggregator Directions 2025

**Layer 4 — Audit**  
Every settlement writes to an immutable audit table in PostgreSQL. Each entry contains the compliance commitment hash, AI risk score, FEMA category, and settlement hash. FIU-IND-compatible STR reports can be generated directly from this table for any transaction scoring above 70. No sensitive user PII appears in any on-chain record.

### 3.2 What makes this different

The distinguishing feature of this protocol relative to other cross-border fintech solutions is that **compliance is proven without being visible**. The FEMA code, LRS amount, and user identity are committed cryptographically but not disclosed on-chain. Any regulator can verify compliance by requesting the preimage from the user — but foreign parties to the transaction (the UAE bank, a BRICS partner country) cannot see the compliance metadata. This is the property that China's digital yuan structurally cannot offer, because the PBOC has surveillance access to e-CNY transactions by design.

This architecture makes the protocol acceptable to BRICS countries that are cautious about replacing dollar dependency with Chinese surveillance dependency. India's neutrality is the competitive advantage.

### 3.3 INR as bridge currency

The protocol supports multi-hop routing: USD → INR → AED. Neither the Canadian sender nor the UAE recipient holds INR. The e-Rupee is used only for settlement — briefly — and the full round-trip is invisible to both end users. This creates genuine demand for INR in international settlement without requiring any country to voluntarily adopt the rupee as a reserve currency.

The SRVA framework already signed by RBI with UAE provides the legal basis. The e₹ Bridge provides the software layer on top.

---

## Section 4 — Technical Architecture

### 4.1 Components built (current state)

| Component | Technology | Status |
|-----------|-----------|--------|
| FEMA Classification Agent | Python, TF-IDF, regex | Complete |
| Risk Scoring Agent | Python, rule engine | Complete |
| Regulatory Q&A Agent | Python, TF-IDF RAG | Complete |
| Customer Service Agent | Python, intent classification | Complete |
| Speed Optimisation Agent | Python, corridor routing | Complete |
| CBDC Bridge Contract | Solidity 0.8.24, OpenZeppelin | Deployed Sepolia |
| ZK Compliance Contract | Solidity, hash commitment | Deployed Sepolia |
| FastAPI Backend | Python, SQLAlchemy, PostgreSQL | Complete |
| User Authentication | JWT, bcrypt | Complete |
| HSM Key Management | Python, ECDSA simulation | Complete |
| CBDC Engine | Python, abstraction layer | Complete (simulated) |
| Multi-sig Coordinator | Python | Complete |

### 4.2 Components to build in sandbox phase

| Component | Technology | Timeline |
|-----------|-----------|---------|
| RBI e-Rupee API integration | REST/gRPC as specified by RBI | Month 1 post-sandbox approval |
| CBUAE Digital Dirham API | REST as published | Month 2 |
| Chainlink INR/AED FX oracle | Solidity, Chainlink | Month 2 |
| Real ZK-SNARK proofs | Circom, snarkjs, Groth16 | Month 3–4 |
| AWS CloudHSM integration | PKCS#11, AWS SDK | Month 2 |
| FIU-IND STR reporting | As per FIU-IND format | Month 3 |
| CERT-In security audit | External auditor | Month 3–4 |

### 4.3 Data localisation

All transaction data is stored on AWS ap-south-1 (Mumbai) or equivalent India-region infrastructure. The PostgreSQL database is deployed in India. The AI agents process all data locally — no user data leaves India for any AI computation. Transaction hashes are posted to Ethereum Sepolia testnet for the sandbox phase; production deployment will use RBI-specified permissioned DLT.

### 4.4 Security architecture

- Passwords: bcrypt hashed, never stored in plain text
- Session tokens: JWT with 24-hour expiry
- PAN: SHA-256 hashed, last 4 digits of Aadhaar only
- API keys: stored in environment variables, never in code
- Transaction signing: ECDSA on secp256k1, HSM-backed in production
- Secret scanning: TruffleHog equivalent runs on every git push
- Smart contract: formal verification planned (Certora) before production
- Multi-sig: 2-of-3 threshold for transfers above ₹1 crore

---

## Section 5 — Regulatory Compliance

### 5.1 Applicable regulations and compliance status

| Regulation | Requirement | Status |
|-----------|-------------|--------|
| FEMA (Current Account Transactions) Rules 2000 | Purpose code on every transfer | Implemented — AI agent enforces |
| RBI Master Direction on LRS | $250,000 annual limit | Hard-enforced in contract and API |
| RBI PA Directions 2025 | ₹25L transaction limit | Hard-enforced in API and contract |
| RBI KYC Master Direction | AML red flags | 8-rule risk agent maps to these flags |
| PMLA 2002 | STR to FIU-IND above thresholds | Audit table supports report generation |
| IT Act 2000 / DPDP Act 2023 | Data localisation | Architecture deploys to India region only |
| RBI Cyber Resilience Directions 2024 | Annual CERT-In audit | Planned for sandbox phase |

### 5.2 What we need from the Regulatory Sandbox

1. **Access to the RBI e-Rupee developer API** — to replace the current simulation with real e-Rupee wallet debit/credit
2. **Regulatory relaxation during test phase** — specifically on the ₹15 crore net worth requirement, for the limited purpose of testing with a defined user cohort
3. **One Authorised Dealer bank partner** — to provide KYC and LRS tracking integration for test users
4. **Guidance on FIU-IND reporting format** — to implement STR generation correctly before graduation
5. **Guidance on permissioned DLT** — which infrastructure RBI specifies for production CBDC settlement

### 5.3 User protection during sandbox

- Maximum transfer amount during test phase: ₹50,000 per transaction
- Maximum cumulative volume during test phase: ₹5 crore
- User cohort: maximum 500 registered users, all KYC-verified
- Geographic scope: India-UAE corridor only during test phase
- Full refund mechanism: any transfer that fails settles within 15 minutes or refunds automatically

---

## Section 6 — Team

### Current

| Name | Role | Background |
|------|------|-----------|
| Abhishek Veda | Founder, Architecture | Full-stack engineer; built complete protocol, AI agents, smart contracts, and security layer |

### Planned hires (post-sandbox approval)

| Role | Priority |
|------|---------|
| ZK Cryptographer (Circom, Groth16) | Critical — required for production ZK proofs |
| Smart Contract Engineer (Solidity, formal verification) | Critical |
| RBI Compliance Specialist (PA-CB, AML, FEMA) | Critical |
| Backend Engineer (Python, PostgreSQL, distributed systems) | High |
| FEMA/PMLA Counsel | High |
| Bank Partnerships BD | High |

### Advisors sought

- Senior FEMA practitioner (practicing CA / CS with AD bank experience)
- Former RBI official (Payments and Settlement Systems department)
- GIFT City IFSC Authority contact

---

## Section 7 — Financial Projections

### Sandbox phase (0–9 months)
- Revenue: Nil (test phase)
- Costs: ₹40–60 lakh (cloud, legal, 2 engineers, CERT-In audit)
- Funding: Bootstrapped + angel investment sought

### Post-sandbox (Year 1)
- Volume target: ₹100 crore per month
- Fee structure: 0.5% retail / 0.3% business / ₹10–50L/month bank licensing
- Revenue at target: ₹1.1–1.5 crore per month

### Scale (Year 2–3)
- Volume target: ₹1,000 crore per month
- Revenue target: ₹10–15 crore per month
- BRICS corridors: UAE, Singapore, Malaysia, Russia, Saudi Arabia

---

## Section 8 — Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| RBI e-Rupee API not available in time | Medium | Protocol designed to work with any CBDC API; timeline adjustable |
| FEMA classification errors | Low | 84% exact match, 96% category accuracy; manual override available |
| Smart contract vulnerability | Low | OpenZeppelin libraries, planned Certora formal verification |
| FX rate manipulation | Low | Chainlink oracle with deviation threshold; fallback to RBI reference rate |
| Data breach | Low | AES-256 at rest, TLS 1.3 in transit, CERT-In audit required |
| Regulatory non-compliance | Low | Every design decision mapped to specific RBI circular |

---

## Section 9 — Sandbox Exit Strategy

At the end of the sandbox test phase (9 months), the outcome will be one of:

**Successful exit:** Apply for full PA-CB authorisation with RBI DPSS. Incorporate India entity (Private Limited). Register with FIU-IND. Appoint grievance officer. Scale to production on India-region cloud.

**Partial exit:** Partner with an existing PA-CB licensed entity as a technology provider, licensing the AI compliance layer and protocol to them.

**Unsuccessful exit:** Open-source the complete protocol and contribute it to the BIS Innovation Hub as India's contribution to global CBDC interoperability research.

---

## Section 10 — The One Ask

We are asking for a Regulatory Sandbox slot to connect this protocol to real e-Rupee infrastructure and test it with real users in the India-UAE corridor.

The code is open source. Every FEMA rule, every compliance decision, every risk flag is auditable. We have built the AI compliance layer that makes the RBI's existing CBDC infrastructure work for cross-border payments. We need the regulatory access to prove it in production.

**Submit to:** fintech@rbi.org.in  
**Regulatory Sandbox portal:** rbi.org.in/Scripts/RegulatoryFrameworkForSandBox.aspx  
**RBIH Showcase:** rbih.org.in · Deadline June 5, 2026

---

*Abhishek Veda · Founder, e₹ Bridge · Toronto, Canada*  
*github.com/Abhishekveda/E-Rupee*  
*Not affiliated with RBI or RBIH. Proof of concept. e-Rupee APIs simulated pending sandbox access.*
