# e₹ Bridge — RBI Compliance & Regulatory Checklist

**Updated against RBI (Regulation of Payment Aggregators) Directions, 2025**  
Effective: September 15, 2025 · Supersedes all prior PA/PA-CB circulars

---

## Status at a Glance

| Requirement | Status in PoC | Path to Production |
|-------------|:------------:|-------------------|
| FIU-IND registration | ⚠ Not applicable (PoC) | Must register before RBI application |
| PA-CB RBI authorisation | ⚠ PoC — not required | Apply via RBI DPSS after FIU-IND registration |
| Net worth ₹15 Cr | ⚠ Not applicable (PoC) | Raise seed round or partner with licensed entity |
| Data localisation (India) | ✓ Architecture supports | Deploy backend on AWS/Azure India region |
| FEMA purpose codes | ✓ Implemented (AI agent) | Live — every transfer has a purpose code |
| LRS limit enforcement | ✓ Risk agent flags breaches | Connect to AD bank for real-time LRS tracking |
| Transaction limit ₹25L | ✓ Enforceable via API | Hard cap in transfer endpoint |
| No fund co-mingling | ✓ Architecture separates | Escrow account per PA-CB requirement |
| CERT-In annual audit | ⚠ Not applicable (PoC) | Engage CERT-In empanelled auditor |
| KYC / Aadhaar eKYC | ⚠ Mock only | Integrate UIDAI eKYC API |
| Grievance officer | ⚠ Not implemented | Appoint named officer, publish on website |
| Cyber Resilience Directions 2024 | ✓ Partially (HTTPS, secrets) | Full pen-test + VAPT report |
| Escrow account | ⚠ Simulated | Open with scheduled commercial bank |
| Fit and proper promoter | ✓ Clean history | Self-declaration + CA certificate |

---

## 1. What you must do before applying to RBI

### Step 1 — Register with FIU-IND (Financial Intelligence Unit India)
This is mandatory and must happen **before** you submit to RBI.

- Portal: [fiuindia.gov.in](https://fiuindia.gov.in)
- Category: Authorised Person under FEMA / Payment Aggregator
- Timeline: 4–6 weeks
- You will be assigned a FIU-IND reporting entity ID

### Step 2 — Incorporate in India
A Canadian entity cannot directly hold a PA-CB licence. Options:
- Incorporate a wholly owned subsidiary in India (Private Limited Company)
- OR partner with an existing PA-CB licensed entity as a technology provider
- The subsidiary route takes 2–3 weeks via MCA portal (mca.gov.in)

### Step 3 — Apply to RBI DPSS
- Portal: [rbi.org.in](https://rbi.org.in) → Payments & Settlement → PA applications
- Attach: incorporation certificate, FIU-IND registration, net worth certificate, tech audit report
- Contact: dpss.co.rbi@rbi.org.in

---

## 2. The PA-CB Rules your application must demonstrate compliance with

### 2.1 Transaction limits
The maximum limit for each transaction is ₹25 lakh for inward or outward payments processed by a PA-CB. Your API already enforces a configurable limit — set this to ₹25,00,000 in production.

### 2.2 Fund segregation
Inward and outward transaction amounts cannot be mixed. Outward transactions should be done only through approved methods. Your architecture keeps these separate — document this explicitly in your application.

### 2.3 Data localisation
All payment system data must be stored in India, per the RBI's 2018 data localisation circular. Deploy the FastAPI backend on an India-region cloud instance (AWS ap-south-1 or Azure Central India).

### 2.4 Net worth requirement
A non-bank entity seeking authorisation must have a minimum net worth of ₹15 crore when applying, and a net worth of ₹25 crore by the end of the third financial year. For a PoC stage, the Regulatory Sandbox waives this requirement — use the Sandbox route.

### 2.5 Grievance redressal
PA-CBs must appoint a grievance redressal officer and carry out security risk assessment to identify risk exposure and remedial measures. Add a named grievance officer to your website and RBIH application.

### 2.6 Fit and proper
Promoters must meet what the regulator calls the 'fit and proper' criteria — a clean financial and regulatory history, a good reputation, and the ability to run financial operations responsibly.

---

## 3. Why the Regulatory Sandbox is your best entry point

The RBI Regulatory Sandbox now operates on an "On Tap" basis — you can apply at any time without waiting for a cohort. The Sandbox:

- Waives the net worth requirement during the test phase
- Grants a limited licence to test with real users (up to 10,000 users or ₹1 Cr volume)
- Does not require CERT-In audit before entry (only before graduation)
- Directly supervised by RBI's Fintech Department

**Your application should explicitly state:** "We are applying for entry into the RBI Regulatory Sandbox under the cross-border CBDC payments category, with a view to obtaining full PA-CB authorisation after sandbox graduation."

Apply at: [rbi.org.in/Scripts/RegulatoryFrameworkForSandBox.aspx](https://rbi.org.in/Scripts/RegulatoryFrameworkForSandBox.aspx)

---

## 4. FEMA compliance (already implemented)

Every transfer in e₹ Bridge carries a FEMA purpose code. The AI agent classifies the purpose automatically and the code is recorded on every transaction record. This satisfies the FEMA (Current Account Transactions) Rules 2000 requirement for purpose documentation.

**For the application, include:**
- Screenshot of the AI agent suggesting P0103 for "university fees in Dubai"
- Screenshot of the FEMA code visible on every transaction receipt
- Explanation of how the agent reduces FEMA errors at source

---

## 5. AML / CFT compliance

The risk agent implements the core AML red flags from RBI's KYC Master Direction:

| RBI Red Flag | e₹ Risk Agent Rule |
|--------------|-------------------|
| Unusually large transfer for stated purpose | `AMOUNT_EXCEEDS_PURPOSE_NORM` |
| LRS limit proximity | `LRS_LIMIT_APPROACHING` / `LRS_LIMIT_EXCEEDED` |
| High transaction velocity | `HIGH_VELOCITY` |
| Cumulative limit breach | `CUMULATIVE_LRS_EXCEEDED` |
| Invalid recipient details | `INVALID_ADDRESS` / `ADDRESS_FORMAT` |

**For production:** Connect to CERSAI (sanctioned entities database) and configure automatic STR (Suspicious Transaction Report) generation to FIU-IND for transactions scoring above 70.

---

## 6. Cyber security requirements

Payment Aggregators must undergo an annual audit by a CERT-In empanelled auditor. The Directions mandate compliance with RBI's Cyber Resilience and Digital Payment Security Directions, 2024.

For the PoC / Sandbox stage, prepare:
- VAPT (Vulnerability Assessment and Penetration Testing) report from any empanelled firm
- Data flow diagram showing where transaction data is stored (India only)
- Incident response procedure document
- Access control policy for the API

---

## 7. Special Rupee Vostro Accounts (SRVA) — the INR bridge currency pathway

The most strategically important compliance pathway for the **USD → INR → AED** corridor is the SRVA framework. The Reserve Bank of India has allowed banks to open Special Rupee Vostro Accounts (SRVAs) without prior approval, promoting INR-based global trade.

An SRVA allows a foreign bank (e.g., a UAE bank) to hold a rupee account with an Indian Authorised Dealer bank. When a Canadian sender initiates a payment:

1. Canadian bank debits CAD / USD from sender
2. Indian AD bank converts to INR via SRVA
3. e₹ Bridge settles in e-Rupee
4. UAE bank's SRVA is credited in INR equivalent
5. UAE recipient receives AED via CBUAE conversion

This eliminates the USD entirely. The INR is the settlement currency. **This is exactly what the RBI is building with Project mBridge and the BRICS CBDC initiative.**

---

## 8. What to write in your RBIH Showcase application

**Problem statement (use these exact phrases — RBI recognises them):**
> "Cross-border CBDC settlement using the e-Rupee as a bridge currency, aligned to RBI's Payments Vision 2025 and the Special Rupee Vostro Account framework."

**Regulatory pathway:**
> "RBI Regulatory Sandbox → PA-CB authorisation → SRVA-integrated production deployment"

**Differentiation:**
> "Custom AI compliance agent that eliminates FEMA purpose code errors at source, implements LRS limit tracking, and generates FIU-IND-compatible risk scores — all without external API dependency."
