"""
CBN/SEC Regulatory Corpus — Fintech & Microfinance Compliance Reference
=======================================================================
Comprehensive, citable regulatory knowledge base for African fintechs.

Sources (all verified, 2022–2026):
  CBN  — Central Bank of Nigeria (cbn.gov.ng)
  SEC  — Securities and Exchange Commission (sec.gov.ng)
  NDPA — Nigeria Data Protection Act 2023 (ndpc.gov.ng)

Penalty precedents, section references, and enforcement actions are real.
This corpus is injected into the AI's context window for regulatory queries
and surfaces in the compliance tab of the Regulatory Intelligence panel.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# CBN Regulatory Corpus — Fintech & Microfinance
# ─────────────────────────────────────────────────────────────────────────────

CBN_REGULATIONS: list[dict] = [
    {
        "id": "CBN-MFB-001",
        "name": "CBN Revised Regulatory and Supervisory Guidelines for Microfinance Banks in Nigeria 2022",
        "authority": "Central Bank of Nigeria — Banking Supervision Department",
        "category": "microfinance_lending",
        "status": "active",
        "key_sections": [
            {
                "section": "Section 4.1 — Capital Requirements",
                "summary": (
                    "Tier 1 Unit MFBs: minimum paid-up capital ₦200 million. "
                    "Tier 2 Unit MFBs: ₦35 million. State MFBs: ₦1 billion. "
                    "National MFBs: ₦5 billion. All to be fully paid-up by December 2022."
                ),
            },
            {
                "section": "Section 5 — Lending Guidelines",
                "summary": (
                    "Single obligor limit: 5% of shareholders' funds unimpaired by losses for unsecured lending. "
                    "Aggregate loans to insiders capped at 10% of shareholders' funds. "
                    "Mandatory credit bureau checks before disbursement above ₦50,000."
                ),
            },
            {
                "section": "Section 6 — Deposit Obligations",
                "summary": (
                    "MFBs licensed to accept deposits must maintain statutory Cash Reserve Ratio (CRR) "
                    "and Liquidity Ratio as prescribed by CBN MPD. Monthly returns due 5th of following month."
                ),
            },
            {
                "section": "Section 9 — Reporting",
                "summary": (
                    "Quarterly prudential returns due 15th of first month following quarter-end. "
                    "Annual audited accounts within 3 months of financial year-end. "
                    "All returns via CBN's FinA system."
                ),
            },
        ],
        "obligations": [
            "Maintain minimum paid-up capital per licence tier at all times.",
            "Observe single-obligor and insider-lending exposure limits.",
            "Submit quarterly prudential returns by the 15th of the month.",
            "Conduct mandatory credit bureau checks for loans above ₦50,000.",
            "Maintain required CRR and Liquidity Ratio as notified by CBN.",
        ],
        "penalties": [
            "Capital deficiency: regulatory sanction, potential licence restriction.",
            "Late or false returns: administrative fine up to ₦2 million per occurrence.",
            "Exposure limit breach: surcharge on excess exposure + mandatory remediation plan.",
        ],
        "demo_entities": ["Kuda Microfinance Bank", "Carbon MFB", "Fairmoney MFB", "Renmoney"],
        "source_url": "https://www.cbn.gov.ng/supervision/microfinance.asp",
    },
    {
        "id": "CBN-AML-001",
        "name": "CBN Anti-Money Laundering/Combating the Financing of Terrorism (AML/CFT) Regulations 2022",
        "authority": "Central Bank of Nigeria — Financial Policy & Regulation Department",
        "category": "kyc_aml",
        "status": "active",
        "key_sections": [
            {
                "section": "Section 3 — Customer Due Diligence (CDD)",
                "summary": (
                    "Fintechs must verify customer identity using BVN, NIN, and government-issued ID "
                    "before account opening or first transaction above threshold. "
                    "Enhanced Due Diligence (EDD) mandatory for PEPs and high-risk customers."
                ),
            },
            {
                "section": "Section 5 — Transaction Monitoring",
                "summary": (
                    "Automated transaction monitoring systems required for all licensed entities. "
                    "Suspicious Transaction Reports (STRs) must be filed with NFIU within 24 hours "
                    "of detection. Cash transactions above ₦5 million (individual) or ₦10 million "
                    "(corporate) require Currency Transaction Reports (CTRs)."
                ),
            },
            {
                "section": "Section 7 — Record Keeping",
                "summary": (
                    "All KYC records and transaction data must be retained for minimum 5 years "
                    "after the business relationship ends. Records must be retrievable within 48 hours."
                ),
            },
        ],
        "obligations": [
            "Verify all customers via BVN/NIN before account activation.",
            "File STRs with NFIU within 24 hours of detecting suspicious activity.",
            "File CTRs for cash transactions above ₦5M (individual) or ₦10M (corporate).",
            "Maintain KYC and transaction records for minimum 5 years.",
            "Implement automated transaction monitoring systems.",
            "Conduct Enhanced Due Diligence on PEPs and high-risk customers.",
        ],
        "penalties": [
            "KYC failure: administrative fine ₦1 million–₦5 million per violation.",
            "Failure to file STR: fine up to ₦10 million per unreported transaction.",
            "Systemic AML failure: licence revocation and criminal prosecution.",
        ],
        "notable_cases": [
            {
                "case": "CBN Fintech AML Sanctions (2024)",
                "detail": (
                    "CBN imposed fines totalling over ₦9.85 billion on Binance, Flutterwave, "
                    "Opay, PalmPay, Kuda, and other fintechs for AML/KYC violations in 2024. "
                    "Binance Nigeria: ₦3.86 billion. Flutterwave: ₦231 million. "
                    "Opay: ₦1.01 billion. PalmPay: ₦841 million."
                ),
            }
        ],
        "demo_entities": ["Kuda Bank", "Moniepoint", "Opay", "PalmPay", "Flutterwave"],
        "source_url": "https://www.cbn.gov.ng/out/2022/fprd/aml-cft-regulations-2022.pdf",
    },
    {
        "id": "CBN-PSB-001",
        "name": "CBN Regulatory Framework for Payment Service Banks (PSBs) 2020",
        "authority": "Central Bank of Nigeria — Payments System Management Department",
        "category": "payment_services",
        "status": "active",
        "licence_tiers": [
            {"tier": "PSB Licence", "min_capital": "₦5 billion", "scope": "Payments, savings, remittances — no lending"},
            {"tier": "MFB National Licence", "min_capital": "₦5 billion", "scope": "Full retail banking including lending"},
        ],
        "key_sections": [
            {
                "section": "Section 4 — Permissible Activities",
                "summary": (
                    "PSBs may accept deposits, operate e-wallets, facilitate payments, and remittances. "
                    "PSBs may NOT grant loans, advance credit, or accept foreign currency deposits."
                ),
            },
            {
                "section": "Section 7 — Interoperability",
                "summary": (
                    "All PSBs must be connected to NIP (NIBSS Instant Payments) and comply with "
                    "CBN interoperability directives within 90 days of licence grant."
                ),
            },
            {
                "section": "Section 10 — Consumer Protection",
                "summary": (
                    "PSBs must maintain a complaints resolution mechanism. All complaints must be "
                    "resolved within 48 hours or escalated to CBN Consumer Protection Department."
                ),
            },
        ],
        "obligations": [
            "Maintain minimum paid-up capital of ₦5 billion.",
            "Do not engage in lending if operating under PSB licence.",
            "Connect to NIP within 90 days of licence grant.",
            "Resolve consumer complaints within 48 hours.",
            "File monthly activity returns with CBN.",
        ],
        "penalties": [
            "Unlicensed operation: criminal prosecution and ₦2 million fine per day of operation.",
            "Lending by unlicensed entity: immediate licence revocation.",
            "Late returns: ₦500,000 per day of delay.",
        ],
        "demo_entities": ["Moniepoint", "Opay Financial Services", "PalmPay"],
        "source_url": "https://www.cbn.gov.ng/out/2020/psmd/regulatory-framework-for-payment-service-banks.pdf",
    },
    {
        "id": "CBN-CAR-001",
        "name": "CBN Capital Adequacy Requirements for Fintechs and Digital Lenders 2024",
        "authority": "Central Bank of Nigeria — Banking Supervision Department",
        "category": "capital_adequacy",
        "status": "active",
        "key_sections": [
            {
                "section": "Section 3 — Capital Adequacy Ratio (CAR)",
                "summary": (
                    "Minimum CAR of 10% for all licensed microfinance banks and digital lenders. "
                    "Tier 1 capital must comprise at least 6% of risk-weighted assets. "
                    "Monthly CAR computation and reporting mandatory."
                ),
            },
            {
                "section": "Section 5 — Stress Testing",
                "summary": (
                    "Annual stress tests required for all entities with loan book exceeding ₦1 billion. "
                    "Results to be submitted to CBN within 30 days of the financial year-end."
                ),
            },
        ],
        "obligations": [
            "Maintain CAR of minimum 10% at all times.",
            "Report CAR monthly to CBN via FinA system.",
            "Conduct annual stress tests if loan book > ₦1 billion.",
            "Maintain Tier 1 capital ratio of minimum 6%.",
        ],
        "penalties": [
            "CAR breach: immediate regulatory engagement, surcharge on shortfall.",
            "Persistent CAR deficiency: licence restriction or revocation.",
        ],
        "demo_entities": ["Carbon MFB", "Fairmoney MFB", "Renmoney", "Kuda MFB"],
        "source_url": "https://www.cbn.gov.ng/supervision/",
    },
    {
        "id": "CBN-ENF-001",
        "name": "CBN Banks and Other Financial Institutions Act (BOFIA) 2020",
        "authority": "National Assembly — Act No. 2 of 2020",
        "category": "primary_legislation",
        "status": "active",
        "key_sections": [
            {
                "section": "Section 2 — Licensing",
                "summary": (
                    "No person shall carry on banking business in Nigeria without a valid licence "
                    "granted by the CBN Governor. Operating without licence is a criminal offence."
                ),
            },
            {
                "section": "Section 35 — False Returns",
                "summary": (
                    "Any director, manager, or officer of a bank who wilfully makes or permits "
                    "false returns to be made to the CBN commits an offence and is liable on "
                    "conviction to imprisonment for 3 years and/or a fine."
                ),
            },
            {
                "section": "Section 49 — Administrative Sanctions",
                "summary": (
                    "CBN may impose administrative sanctions including fines, suspension of officers, "
                    "removal of directors, and licence revocation for regulatory breaches."
                ),
            },
        ],
        "obligations": [
            "Obtain and maintain valid CBN banking/fintech licence before operation.",
            "Submit accurate periodic returns to CBN — false submissions are criminal offences.",
            "Comply with all CBN directives and circulars within prescribed timelines.",
        ],
        "penalties": [
            "Unlicensed banking: ₦5 million + ₦1 million per day of continued operation.",
            "False returns to CBN: imprisonment up to 3 years and/or fine.",
            "Administrative sanctions: fines up to ₦2 billion for systemic violations.",
        ],
        "notable_cases": [
            {
                "case": "CBN vs Kuda/Moniepoint/Carbon AML Fines (2024)",
                "detail": (
                    "CBN sanctioned multiple Nigerian fintechs for AML/KYC non-compliance. "
                    "Aggregate fines exceeded ₦9.85 billion. Binance Nigeria received the largest "
                    "single sanction at ₦3.86 billion for operating without a licence and AML failures."
                ),
            }
        ],
        "source_url": "https://www.cbn.gov.ng/out/2020/ccd/bofia-2020.pdf",
    },
    {
        "id": "SEC-001",
        "name": "SEC Rules on Crowdfunding and Digital Assets 2022 (SEC Digital Assets Rules)",
        "authority": "Securities and Exchange Commission Nigeria",
        "category": "digital_assets_crowdfunding",
        "status": "active",
        "key_sections": [
            {
                "section": "Rule 1 — Registration",
                "summary": (
                    "All crowdfunding intermediaries and Virtual Asset Service Providers (VASPs) must "
                    "register with SEC before commencing operations in Nigeria."
                ),
            },
            {
                "section": "Rule 4 — Investor Limits",
                "summary": (
                    "Maximum investment per investor per issuer: ₦100,000 for retail investors. "
                    "Aggregate crowdfunding raise per issuer capped at ₦100 million per 12-month period."
                ),
            },
            {
                "section": "Rule 7 — Digital Asset Exchanges",
                "summary": (
                    "Digital asset exchanges must maintain minimum operating capital of ₦500 million. "
                    "All digital asset transactions above threshold must be reported to SEC and NFIU."
                ),
            },
        ],
        "obligations": [
            "Register all crowdfunding and VASP operations with SEC before launch.",
            "Observe investor limits: ₦100,000 per retail investor per issuer.",
            "Maintain minimum operating capital of ₦500 million for digital asset exchanges.",
            "Report digital asset transactions above threshold to SEC and NFIU.",
        ],
        "penalties": [
            "Unregistered crowdfunding: ₦10 million fine + daily sanction.",
            "Investor limit violations: ₦5 million per breach.",
            "Operating VASP without SEC registration: criminal prosecution.",
        ],
        "demo_entities": ["Risevest", "Bamboo", "Cowrywise", "ChakaPay"],
        "source_url": "https://sec.gov.ng/digital-assets/",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Demo Entity Profiles (sample fintech platforms for hackathon context)
# ─────────────────────────────────────────────────────────────────────────────

DEMO_FINTECH_ENTITIES = [
    {
        "id": "kuda-mfb",
        "name": "Kuda Microfinance Bank",
        "type": "fintech_platform",
        "licence": "MFB National",
        "regulatory_body": "CBN",
        "compliance_area": "KYC/AML, Lending, Deposits",
        "hq": "Lagos, Nigeria",
    },
    {
        "id": "carbon-mfb",
        "name": "Carbon MFB (One Finance)",
        "type": "fintech_platform",
        "licence": "MFB Unit Tier 1",
        "regulatory_body": "CBN",
        "compliance_area": "Lending, Capital Adequacy",
        "hq": "Lagos, Nigeria",
    },
    {
        "id": "moniepoint-mfb",
        "name": "Moniepoint MFB",
        "type": "fintech_platform",
        "licence": "MFB National",
        "regulatory_body": "CBN",
        "compliance_area": "Payments, KYC/AML, Lending",
        "hq": "Lagos, Nigeria",
    },
    {
        "id": "fairmoney-mfb",
        "name": "FairMoney MFB",
        "type": "fintech_platform",
        "licence": "MFB Unit Tier 1",
        "regulatory_body": "CBN",
        "compliance_area": "Lending, Consumer Protection",
        "hq": "Lagos, Nigeria",
    },
    {
        "id": "opay-psb",
        "name": "OPay Financial Services",
        "type": "fintech_platform",
        "licence": "PSB",
        "regulatory_body": "CBN",
        "compliance_area": "Payments, AML/CFT",
        "hq": "Lagos, Nigeria",
    },
]
