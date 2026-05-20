"""
knowledge_base.py
=================
The e₹ Bridge AI Agent's knowledge base.

Contains:
  1. All RBI-published FEMA purpose codes (400+, summarised to the most
     relevant remittance categories for the India-UAE/SG corridor)
  2. RBI regulatory excerpts — LRS rules, FEMA Master Direction, e-Rupee pilot
  3. Common user intent patterns mapped to each purpose code

This file is the "memory" of the AI agent.  It is loaded once at startup
and queried by all three sub-agents (FEMA, Risk, QA).

Source documents:
  - RBI Master Direction on Liberalised Remittance Scheme (2023)
  - FEMA (Current Account Transactions) Rules 2000
  - RBI e-Rupee Concept Note (2022)
  - RBI Payments Vision 2025
"""

# ── FEMA PURPOSE CODES ────────────────────────────────────────────────────────
# Each entry: code, category, description, user_keywords, examples, lrs_note

FEMA_CODES = [
    {
        "code": "P0101",
        "category": "Private transfers",
        "description": "Remittance towards family maintenance",
        "keywords": ["family", "maintenance", "support", "parents", "mother", "father",
                     "spouse", "children", "relatives", "household", "living expenses",
                     "send to family", "send money home"],
        "examples": [
            "sending money to my parents in India",
            "monthly support for my family",
            "household expenses for my wife",
        ],
        "lrs_note": "Permitted under LRS up to $250,000 per financial year.",
        "typical_range_inr": (1000, 1000000),
    },
    {
        "code": "P0102",
        "category": "Private transfers",
        "description": "Remittance towards maintenance of close relatives abroad",
        "keywords": ["relative", "close relative", "brother", "sister", "uncle",
                     "aunt", "cousin", "maintenance abroad", "living abroad"],
        "examples": [
            "supporting my sister studying abroad",
            "maintenance for my brother working overseas",
        ],
        "lrs_note": "Permitted under LRS up to $250,000 per financial year.",
        "typical_range_inr": (1000, 500000),
    },
    {
        "code": "P0103",
        "category": "Education",
        "description": "Remittances for studies abroad",
        "keywords": ["university", "college", "school", "tuition", "education",
                     "study", "studies", "fees", "course", "degree", "MBA", "masters",
                     "PhD", "bachelor", "enrollment", "admission", "semester",
                     "hostel fees", "accommodation fees", "student"],
        "examples": [
            "paying university fees in Dubai",
            "tuition for my daughter's MBA at a foreign university",
            "college enrollment fees abroad",
            "paying school fees for my child studying overseas",
        ],
        "lrs_note": "Education remittances are specifically permitted under LRS. "
                    "Includes tuition, hostel, and related academic expenses.",
        "typical_range_inr": (50000, 5000000),
    },
    {
        "code": "P0104",
        "category": "Travel",
        "description": "Travel — business or personal",
        "keywords": ["travel", "trip", "holiday", "vacation", "business trip",
                     "flight", "hotel", "accommodation", "tourism", "visit"],
        "examples": [
            "travel expenses for my Dubai trip",
            "hotel and flight booking for vacation",
        ],
        "lrs_note": "Travel remittances permitted under LRS.",
        "typical_range_inr": (5000, 500000),
    },
    {
        "code": "P0105",
        "category": "Private transfers",
        "description": "Gift remittance",
        "keywords": ["gift", "gifting", "present", "birthday", "wedding gift",
                     "festival", "celebration", "diwali", "eid", "christmas"],
        "examples": [
            "sending a gift to my friend abroad",
            "Diwali gift transfer",
        ],
        "lrs_note": "Gift remittances permitted under LRS up to $250,000/year.",
        "typical_range_inr": (500, 200000),
    },
    {
        "code": "P0106",
        "category": "Private transfers",
        "description": "Donation to foreign charitable organisations",
        "keywords": ["donation", "charity", "NGO", "non-profit", "philanthropic",
                     "contribution", "fund", "humanitarian"],
        "examples": [
            "donation to a charity abroad",
            "contribution to an international NGO",
        ],
        "lrs_note": "Donations to foreign charities permitted under LRS.",
        "typical_range_inr": (1000, 1000000),
    },
    {
        "code": "P0801",
        "category": "Medical",
        "description": "Medical treatment abroad",
        "keywords": ["medical", "hospital", "doctor", "surgery", "treatment",
                     "healthcare", "medicine", "clinic", "specialist", "health",
                     "therapy", "diagnosis", "operation", "procedure"],
        "examples": [
            "medical treatment in Singapore hospital",
            "paying for surgery abroad",
            "specialist consultation fees overseas",
        ],
        "lrs_note": "Medical treatment abroad is permitted under LRS.",
        "typical_range_inr": (10000, 5000000),
    },
    {
        "code": "P0802",
        "category": "Medical",
        "description": "Maintenance expenses of patient going abroad for medical treatment",
        "keywords": ["patient", "caretaker", "accompanying", "escort", "attendant",
                     "medical trip expenses", "travel for treatment"],
        "examples": [
            "expenses for accompanying patient to Dubai hospital",
        ],
        "lrs_note": "Permitted as part of medical treatment LRS allowance.",
        "typical_range_inr": (10000, 500000),
    },
    {
        "code": "P1001",
        "category": "Software and IT services",
        "description": "Computer software services — export receipts / payments",
        "keywords": ["software", "IT", "technology", "development", "programming",
                     "SaaS", "cloud", "subscription", "license", "tech services"],
        "examples": [
            "paying for software license abroad",
            "SaaS subscription payment",
        ],
        "lrs_note": "Business/IT service payments — may require additional documentation.",
        "typical_range_inr": (1000, 10000000),
    },
    {
        "code": "P1301",
        "category": "Business services",
        "description": "Payments for business and professional services",
        "keywords": ["business", "invoice", "vendor", "supplier", "consultant",
                     "professional", "service", "contract", "freelancer", "payment",
                     "trade", "commercial", "B2B", "company"],
        "examples": [
            "paying a foreign vendor invoice",
            "consultant fees for overseas professional",
            "B2B payment for services rendered",
        ],
        "lrs_note": "Business service payments require supporting documentation "
                    "(invoice, contract). May require AD bank approval above thresholds.",
        "typical_range_inr": (5000, 50000000),
    },
    {
        "code": "P1302",
        "category": "Business services",
        "description": "Legal services",
        "keywords": ["legal", "lawyer", "attorney", "solicitor", "law firm",
                     "litigation", "court", "legal fees"],
        "examples": ["paying legal fees to a foreign law firm"],
        "lrs_note": "Legal service payments — require invoice documentation.",
        "typical_range_inr": (10000, 5000000),
    },
    {
        "code": "P1303",
        "category": "Business services",
        "description": "Management consulting services",
        "keywords": ["consulting", "management", "advisory", "strategy", "McKinsey",
                     "Deloitte", "BCG", "management fees"],
        "examples": ["management consulting fees to overseas firm"],
        "lrs_note": "Consulting payments — require service agreement.",
        "typical_range_inr": (50000, 10000000),
    },
    {
        "code": "P0301",
        "category": "Transport",
        "description": "Freight and shipping charges",
        "keywords": ["freight", "shipping", "cargo", "logistics", "transport",
                     "courier", "delivery"],
        "examples": ["paying freight charges for shipment"],
        "lrs_note": "Freight payments for goods imports/exports.",
        "typical_range_inr": (5000, 5000000),
    },
]

# Build lookup dict for fast access
FEMA_CODE_LOOKUP = {fc["code"]: fc for fc in FEMA_CODES}


# ── RBI REGULATORY KNOWLEDGE ──────────────────────────────────────────────────
# Used by the Q&A agent via RAG retrieval

RBI_KNOWLEDGE_CHUNKS = [
    {
        "id": "lrs_001",
        "topic": "LRS annual limit",
        "content": "Under the Liberalised Remittance Scheme (LRS), resident individuals "
                   "may remit up to USD 250,000 per financial year (April to March) for "
                   "any permitted current or capital account transactions. This limit was "
                   "revised to USD 250,000 by RBI vide AP (DIR Series) Circular No. 138 "
                   "dated June 3, 2014. The limit is per individual, per financial year.",
        "source": "RBI Master Direction on LRS (2023)",
    },
    {
        "id": "lrs_002",
        "topic": "LRS prohibited transactions",
        "content": "Remittances under LRS are NOT permitted for: (a) purchase of lottery "
                   "tickets, banned magazines or items. (b) trading in foreign exchange "
                   "abroad. (c) capital account remittances to countries identified by FATF "
                   "as non-cooperative. (d) purchase of Foreign Currency Convertible Bonds "
                   "issued by Indian companies. (e) remittances to Nepal and Bhutan are "
                   "not permitted under LRS.",
        "source": "RBI Master Direction on LRS (2023)",
    },
    {
        "id": "lrs_003",
        "topic": "LRS permitted capital account transactions",
        "content": "Under LRS, resident individuals can make remittances for: opening of "
                   "foreign currency accounts abroad with a bank; purchase of property "
                   "abroad; making investments abroad; setting up wholly owned "
                   "subsidiaries and joint ventures abroad (subject to conditions); "
                   "extending loans to Non-Resident Indians (NRIs).",
        "source": "RBI Master Direction on LRS (2023)",
    },
    {
        "id": "fema_001",
        "topic": "FEMA purpose codes overview",
        "content": "FEMA purpose codes are mandatory classifications for all cross-border "
                   "remittances under India's Foreign Exchange Management Act. Every "
                   "outward/inward remittance must be tagged with a purpose code. The codes "
                   "are maintained by RBI and range from P0101 (family maintenance) to "
                   "codes covering education, medical, travel, investment, and business "
                   "services. Incorrect purpose codes can trigger RBI compliance reviews "
                   "and delays.",
        "source": "FEMA (Current Account Transactions) Rules 2000",
    },
    {
        "id": "fema_002",
        "topic": "Education remittance FEMA code",
        "content": "P0103 is the FEMA purpose code for remittances for studies abroad. "
                   "This includes tuition fees, hostel fees, examination fees, and other "
                   "direct education-related costs. The remitter must be the student or "
                   "the student's parent/guardian. Supporting documents such as admission "
                   "letter and fee demand notice from the foreign institution are typically "
                   "required by the Authorised Dealer bank.",
        "source": "RBI Circular on FEMA Purpose Codes",
    },
    {
        "id": "fema_003",
        "topic": "Medical treatment remittance",
        "content": "P0801 covers remittances for medical treatment abroad. This includes "
                   "hospital fees, doctor consultation charges, surgical expenses, and "
                   "associated medical costs. Authorised Dealers may ask for supporting "
                   "documents such as a medical certificate or hospital appointment letter. "
                   "The accompanying attendant's expenses may also be covered under P0802.",
        "source": "RBI Circular on FEMA Purpose Codes",
    },
    {
        "id": "cbdc_001",
        "topic": "e-Rupee CBDC overview",
        "content": "The Reserve Bank of India launched the e-Rupee (e₹) CBDC pilot in "
                   "December 2022. The e₹-R (retail) variant targets everyday transactions "
                   "for individuals and businesses. As of March 2025, over 60 lakh (6 "
                   "million) users across 17 banks are participating in the pilot. The "
                   "e-Rupee is a legal tender equivalent to physical currency, issued "
                   "directly by RBI.",
        "source": "RBI e-Rupee Concept Note (2022) and Pilot Updates",
    },
    {
        "id": "cbdc_002",
        "topic": "e-Rupee cross-border potential",
        "content": "RBI Deputy Governor T. Rabi Sankar stated at Global Fintech Fest 2025: "
                   "The basic use case for CBDC eventually comes in the cross-border space. "
                   "We have to get into a few cross-border arrangements. The RBI is "
                   "actively engaged with BIS through Project Dunbar and Project Nexus "
                   "to establish CBDC-based cross-border payment infrastructure between "
                   "India and partner countries including UAE and Singapore.",
        "source": "RBI Deputy Governor speech, GFF 2025",
    },
    {
        "id": "cbdc_003",
        "topic": "e-Rupee wholesale pilot",
        "content": "The e₹-W (wholesale) CBDC is designed for interbank settlements and "
                   "large-value transactions between financial institutions. It uses the "
                   "NDS-OM (Negotiated Dealing System - Order Matching) infrastructure. "
                   "The wholesale pilot involves nine banks: SBI, Bank of Baroda, Union "
                   "Bank, HDFC Bank, ICICI Bank, Kotak Mahindra Bank, YES Bank, IDFC "
                   "First Bank, and HSBC.",
        "source": "RBI e-Rupee Concept Note (2022)",
    },
    {
        "id": "remittance_001",
        "topic": "India remittance statistics",
        "content": "India is the world's largest recipient of remittances. According to "
                   "World Bank data 2024, India received over $100 billion in inward "
                   "remittances. The UAE is the largest source corridor ($18 billion), "
                   "followed by the United States, United Kingdom, Canada, and Singapore. "
                   "The Indian diaspora in Canada exceeds 1.6 million people. Average "
                   "remittance cost via SWIFT is 6.3%, compared to a global target of "
                   "3% under the UN Sustainable Development Goals.",
        "source": "World Bank Remittance Prices Worldwide (2024)",
    },
    {
        "id": "sandbox_001",
        "topic": "RBI Regulatory Sandbox",
        "content": "The RBI Regulatory Sandbox (RS) allows live testing of new financial "
                   "products in a controlled environment. As of April 2025, RBI proposed "
                   "making the Sandbox Theme Neutral and On Tap — meaning applications "
                   "can be submitted at any time for any innovative financial technology "
                   "within RBI's regulatory ambit. Previous cohorts covered retail "
                   "payments, cross-border payments (Cohort 2), MSME lending, and "
                   "prevention of financial fraud. Contact: fintech@rbi.org.in",
        "source": "RBI Developmental and Regulatory Policies Statement, April 2025",
    },
    {
        "id": "payments_vision_001",
        "topic": "RBI Payments Vision 2025",
        "content": "RBI's Payments Vision 2025 document outlines the goal of establishing "
                   "India as a leading country in payment systems globally. Key objectives "
                   "include: enabling cross-border CBDC payments, expanding UPI "
                   "internationally, promoting interoperability between domestic and "
                   "foreign payment systems, and ensuring regulatory clarity for fintech "
                   "innovation. The vision explicitly mentions CBDC as a tool for "
                   "cross-border settlement efficiency.",
        "source": "RBI Payments Vision 2025 (June 2022)",
    },
    {
        "id": "aml_001",
        "topic": "AML and FEMA compliance for remittances",
        "content": "Authorised Dealer banks must comply with RBI's Know Your Customer "
                   "(KYC) and Anti-Money Laundering (AML) guidelines for all outward "
                   "remittances. Under PMLA (Prevention of Money Laundering Act), "
                   "suspicious transactions must be reported to FIU-IND (Financial "
                   "Intelligence Unit India). Red flags include: structuring transactions "
                   "below reporting thresholds, mismatched purpose codes, frequent "
                   "transfers to new recipients, and amounts inconsistent with sender's "
                   "declared income.",
        "source": "RBI Master Direction on KYC (2016, amended 2023)",
    },
]
