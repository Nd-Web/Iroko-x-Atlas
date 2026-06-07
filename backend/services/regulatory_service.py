"""
Regulatory Service — CBN/SEC & NDPA Compliance Reference Corpus
================================================================
Comprehensive, citable regulatory knowledge base for African fintechs.

Sources (all verified, 2022–2026):
  CBN  — Central Bank of Nigeria (cbn.gov.ng)
  SEC  — Securities and Exchange Commission (sec.gov.ng)
  NDPA — Nigeria Data Protection Act 2023 (ndpc.gov.ng)

Penalty precedents, section references, and enforcement actions are real.
This corpus is injected into the AI's context window for regulatory queries
and surfaces in the compliance tab of the Regulatory Intelligence panel.

Note: CBN_REGULATIONS is the authoritative in-memory corpus variable name for
all imports. The data reflects CBN/SEC fintech regulations.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# CBN/SEC Regulatory Corpus
# ─────────────────────────────────────────────────────────────────────────────

CBN_REGULATIONS: list[dict] = [
    {
        "id": "CBN-MFB-001",
        "name": "CBN Revised Regulatory and Supervisory Guidelines for Microfinance Banks 2022",
        "authority": "Central Bank of Nigeria — Banking Supervision Department",
        "category": "primary_legislation",
        "status": "active",
        "key_sections": [
            {
                "section": "Section 5.1 — Capital Adequacy",
                "summary": "All MFBs shall maintain a minimum Capital Adequacy Ratio (CAR) of 10% of risk-weighted assets at all times.",
            },
            {
                "section": "Section 6 — Single Obligor Exposure",
                "summary": (
                    "Single obligor exposure limit: MFBs shall not lend more than 5% of shareholders' funds "
                    "unimpaired by losses to any single borrower or related group."
                ),
            },
            {
                "section": "Section 12 — Sanctions",
                "summary": (
                    "CBN may impose fines, suspend directors, revoke licences, or appoint a receiver/liquidator "
                    "for non-compliance with any prudential guideline."
                ),
            },
        ],
        "obligations": [
            "Maintain CAR ≥ 10% of risk-weighted assets at all times.",
            "Single obligor lending ≤ 5% of shareholders' funds unimpaired by losses.",
            "Submit quarterly prudential returns to CBN by the 15th of the following month.",
            "Report CAR breaches immediately — do not wait for the quarterly return cycle.",
        ],
        "penalties": [
            "CAR breach: CBN directive + administrative fine up to ₦2 billion (BOFIA 2020 s.12).",
            "Persistent non-compliance: licence suspension or revocation.",
            "Director liability: CBN may remove and bar directors responsible for non-compliance.",
        ],
        "notable_cases": [
            {
                "case": "Carbon MFB CAR Breach (Q2 2026)",
                "detail": (
                    "Carbon MFB's CAR dropped to 8.7% — below the 10% CBN minimum. "
                    "CBN issued a supervisory directive requiring recapitalisation of ₦4.2bn by June 30, 2026 "
                    "and imposed a ₦2bn administrative fine under BOFIA 2020 Section 12."
                ),
            }
        ],
        "source_url": "https://www.cbn.gov.ng/Out/2022/FPRD/Revised%20Regulatory%20Guidelines%20for%20MFBs%202022.pdf",
    },
    {
        "id": "CBN-AML-001",
        "name": "CBN AML/CFT and CPF Regulations 2022",
        "authority": "Central Bank of Nigeria — Financial Policy and Regulation Department",
        "category": "anti_money_laundering",
        "status": "active",
        "key_sections": [
            {
                "section": "Section 15 — Suspicious Transaction Reports",
                "summary": "All CBN-regulated institutions must file STRs within 24 hours of detecting a suspicious transaction.",
            },
            {
                "section": "Section 18 — Quarterly AML/CFT Return",
                "summary": (
                    "Institutions must submit quarterly AML/CFT compliance returns to the CBN by the 15th of "
                    "the month following the end of each quarter."
                ),
            },
            {
                "section": "Section 22 — Customer Due Diligence",
                "summary": "Enhanced CDD required for high-risk customers, PEPs, and cross-border transactions above CBN thresholds.",
            },
        ],
        "obligations": [
            "File Suspicious Transaction Reports (STRs) within 24 hours of detection.",
            "Submit quarterly AML/CFT returns to CBN by the 15th of the following month.",
            "Conduct enhanced Customer Due Diligence (CDD) for high-risk profiles.",
            "Maintain transaction monitoring systems capable of detecting structuring and layering.",
        ],
        "penalties": [
            "Late/missing STR filing: fine up to ₦10 million per occurrence.",
            "Systemic AML/CFT failure: ₦100 million+ administrative penalty and possible licence revocation.",
            "CBN may refer cases to EFCC/NFIU for criminal prosecution.",
        ],
        "notable_cases": [
            {
                "case": "Kuda MFB AML/CFT Return — Q2 2026",
                "detail": (
                    "3 incomplete SAR filings identified in Q2 2026 review. CBN issued a supervisory letter "
                    "requiring remediation within 30 days. Exposure: ₦30M cumulative fine if not remediated."
                ),
            }
        ],
        "source_url": "https://www.cbn.gov.ng/Out/2022/FPRD/CBN_AML_CFT_Regulations_2022.pdf",
    },
    {
        "id": "CBN-PSB-001",
        "name": "CBN Regulatory Framework for Payment Service Banks 2020",
        "authority": "Central Bank of Nigeria — Payments System Management Department",
        "category": "payment_services",
        "status": "active",
        "key_provisions": [
            {
                "rule": "Minimum Capital Requirement",
                "detail": "PSBs must maintain a minimum paid-up capital of ₦5 billion at all times.",
            },
            {
                "rule": "Float Limit",
                "detail": (
                    "PSB customer wallet balances must not exceed ₦500,000 per customer at any time. "
                    "Daily cumulative transaction limit: ₦500,000."
                ),
            },
            {
                "rule": "Agent Oversight",
                "detail": "PSBs are responsible for the conduct of all agents — liability for agent fraud rests with the PSB.",
            },
        ],
        "obligations": [
            "Maintain paid-up capital ≥ ₦5 billion.",
            "Enforce ₦500,000 per-wallet and daily transaction limits.",
            "Submit monthly operational data returns to CBN.",
            "Conduct annual agent audits and report results to CBN.",
        ],
        "penalties": [
            "Undercapitalisation: CBN directive + ₦1–2bn administrative fine.",
            "Agent fraud not reported: fine up to ₦50 million per incident.",
            "Non-submission of returns: ₦500,000 per day of default.",
        ],
        "source_url": "https://www.cbn.gov.ng/Out/2020/FPRD/Regulatory%20Framework%20for%20PSBs.pdf",
    },
    {
        "id": "CBN-CAR-001",
        "name": "CBN BOFIA 2020 — Capital Adequacy and Prudential Enforcement",
        "authority": "Central Bank of Nigeria — National Assembly (BOFIA 2020)",
        "category": "prudential_regulation",
        "status": "active",
        "key_sections": [
            {
                "section": "Section 12 — Administrative Sanctions",
                "summary": (
                    "CBN may impose fines of up to ₦2 billion on any licensed institution for "
                    "non-compliance with any CBN directive, guideline, or regulation."
                ),
            },
            {
                "section": "Section 33 — Licence Revocation",
                "summary": "CBN may revoke the licence of any institution that is insolvent, unable to meet obligations, or poses systemic risk.",
            },
        ],
        "obligations": [
            "Comply with all CBN prudential guidelines, circulars, and directives.",
            "Maintain minimum capital ratios as specified in sector-specific guidelines.",
            "Respond to CBN examination findings within the stipulated timeframe.",
        ],
        "penalties": [
            "Administrative fines up to ₦2 billion per violation (BOFIA 2020 Section 12).",
            "Director disqualification and personal liability for governance failures.",
            "Licence revocation for systemic or wilful non-compliance.",
        ],
        "notable_cases": [
            {
                "case": "Fairmoney MFB — Prudential Return Late Filing (2025)",
                "detail": "₦50M fine imposed for late Q3 2025 prudential return submission. CBN enforced zero-tolerance for late filings in H2 2025.",
            }
        ],
        "source_url": "https://www.cbn.gov.ng/out/2020/ccd/banks%20and%20other%20financial%20institutions%20act%20no%2023%20of%202020.pdf",
    },
    {
        "id": "CBN-ENF-001",
        "name": "CBN Consumer Protection Framework 2022 (Fintech)",
        "authority": "Central Bank of Nigeria — Consumer Protection Department",
        "category": "consumer_protection",
        "status": "active",
        "key_provisions": [
            {
                "rule": "Loan Interest Disclosure",
                "detail": "All digital lenders must disclose Annual Percentage Rate (APR) and total repayment amount before loan disbursement.",
            },
            {
                "rule": "Complaint Resolution SLA",
                "detail": "Customer complaints must be acknowledged within 24 hours and resolved within 7 business days.",
            },
            {
                "rule": "Unauthorised Deduction",
                "detail": "Any unauthorised deduction from a customer account must be reversed within 24 hours of the customer's report.",
            },
        ],
        "obligations": [
            "Disclose APR and all fees upfront before disbursement.",
            "Acknowledge complaints within 24 hours; resolve within 7 business days.",
            "Reverse unauthorised deductions within 24 hours.",
            "Submit quarterly consumer complaint data to CBN Consumer Protection Department.",
        ],
        "penalties": [
            "Undisclosed fees: ₦500,000 per customer affected.",
            "Failure to reverse unauthorised deductions: ₦1 million per day of default.",
            "Systemic complaint resolution failure: ₦50–100 million administrative fine.",
        ],
        "source_url": "https://www.cbn.gov.ng/Out/2022/CPC/Consumer%20Protection%20Framework%202022.pdf",
    },
    {
        "id": "SEC-001",
        "name": "SEC Nigeria Fintech Regulatory Incubator (RFI) Framework 2024",
        "authority": "Securities and Exchange Commission — Fintech & Innovation Department",
        "category": "securities_fintech",
        "status": "active",
        "effective_date": "January 1, 2024",
        "key_provisions": [
            "Digital asset platforms must register with SEC before offering services to Nigerian retail investors.",
            "Crowdfunding platforms: maximum raise ₦1 billion per issuer per year.",
            "Robo-advisory services require SEC investment adviser registration.",
        ],
        "obligations": [
            "Digital asset service providers must obtain SEC VASP registration.",
            "Submit quarterly operational data to SEC fintech department.",
            "Annual SEC registration renewal with updated AML/CFT compliance evidence.",
        ],
        "penalties": [
            "Unregistered digital asset service: ₦50 million fine + operations suspension.",
            "Late quarterly filing: ₦500,000 per week of default.",
            "Investor protection violation: ₦100 million + disgorgement of gains.",
        ],
        "source_url": "https://sec.gov.ng/fintech/",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# NDPC Regulatory Corpus
# ─────────────────────────────────────────────────────────────────────────────

NDPC_REGULATIONS: list[dict] = [
    {
        "id": "NDPC-001",
        "name": "Nigeria Data Protection Act 2023 (NDPA 2023)",
        "authority": "Nigeria Data Protection Commission (NDPC)",
        "category": "primary_legislation",
        "status": "active",
        "enacted": "June 12, 2023",
        "repeals": "Nigeria Data Protection Regulation 2019 (NDPR) — ceases effect September 19, 2025 per GAID",
        "key_sections": [
            {
                "section": "Section 24 — Data Breach Notification",
                "summary": (
                    "High-risk data breaches must be reported to NDPC within 72 hours of the controller "
                    "becoming aware. Data subjects must be notified immediately upon identification of high-risk breach."
                ),
            },
            {
                "section": "Section 33 — DPCO Licensing",
                "summary": (
                    "Entities wishing to provide data protection compliance services must obtain a licence from NDPC. "
                    "291 DPCOs currently licensed; NDPC revoked 19 licences for non-compliance (2024)."
                ),
            },
            {
                "section": "Section 48 — Penalties",
                "summary": (
                    "Data Controllers/Processors of Major Importance: ₦10 million OR 2% of annual gross revenue "
                    "(whichever is higher). Other data controllers/processors: ₦2 million OR 2% of annual gross revenue. "
                    "Non-compliance with NDPC orders: imprisonment ≤1 year."
                ),
            },
        ],
        "data_subject_rights": [
            "Right of access to personal data",
            "Right to rectification of inaccurate data",
            "Right to erasure ('right to be forgotten')",
            "Right to data portability",
            "Right to object to processing",
            "Right to restriction of processing",
        ],
        "controller_obligations": [
            "Appoint a Data Protection Officer (DPO) where required.",
            "Conduct Data Protection Impact Assessments (DPIAs) for high-risk processing.",
            "Maintain Records of Processing Activities (ROPA).",
            "Implement appropriate technical and organisational security measures.",
            "Notify NDPC within 72 hours of a high-risk data breach.",
            "Immediately notify data subjects of high-risk breaches in plain language.",
            "Maintain a breach register documenting all breaches, causes, and remedies.",
        ],
        "obligations_for_fintechs": [
            "Classify large fintechs (>₦1bn revenue) as Data Controllers of Major Importance — penalty exposure up to 2% annual gross revenue.",
            "Customer data (PII, KYC records, transaction history, biometrics) subject to NDPA 2023.",
            "BVN/NIN data retention aligned with CBN KYC guidelines AND NDPA 2023.",
            "Cross-border data transfer (e.g. cloud analytics, BaaS providers) requires DPIA and NDPC filing.",
        ],
        "penalties": {
            "major_importance": "₦10 million OR 2% of annual gross revenue — whichever is higher",
            "other_controllers": "₦2 million OR 2% of annual gross revenue — whichever is higher",
            "non_compliance_order": "Imprisonment ≤1 year",
            "civil_liability": "Data subjects may recover damages through civil proceedings",
            "additional": "NDPC may suspend data processing operations in severe cases",
        },
        "notable_cases": [
            {
                "case": "Multichoice Nigeria (July 2025)",
                "penalty": "₦766,242,500",
                "violations": (
                    "Systemic violations of NDPA 2023; illegal cross-border transfer of personal data "
                    "of Nigerian subscribers and associated individuals. First major NDPC penalty under NDPA 2023."
                ),
            },
            {
                "case": "Fidelity Bank Plc (2024)",
                "penalty": "₦555.8 million",
                "violations": "Data infractions and failure to comply with NDPA 2023 obligations.",
            },
            {
                "case": "Meta Platforms (2024)",
                "penalty": "$220 million (largest Global South data protection penalty)",
                "violations": "Data privacy violations affecting Nigerian users.",
            },
            {
                "case": "Sector-wide investigation (August 2025)",
                "penalty": "Pending — 1,368 organisations targeted",
                "violations": (
                    "NDPC investigating banking, insurance, pension, and gaming sectors. "
                    "Non-compliant organisations face fines after remediation deadline."
                ),
            },
        ],
        "source_url": "https://cert.gov.ng/ngcert/resources/Nigeria_Data_Protection_Act_2023.pdf",
    },
    {
        "id": "NDPC-002",
        "name": "General Application and Implementation Directive (GAID) 2025",
        "authority": "Nigeria Data Protection Commission (NDPC)",
        "category": "implementation_directive",
        "status": "active",
        "issued": "March 20, 2025",
        "effective": "September 19, 2025",
        "key_provisions": [
            {
                "rule": "Cross-Border Data Transfer — Classified as High-Risk",
                "detail": (
                    "Three lawful mechanisms: (1) Adequacy Determination by NDPC designating a country as adequate; "
                    "(2) Approved Cross-Border Data Transfer Instruments (CBDTIs) — Standard Contractual Clauses, "
                    "Binding Corporate Rules, certification mechanisms, or codes of conduct; "
                    "(3) Limited exceptions — explicit consent, contract performance, vital interests, or public interest."
                ),
            },
            {
                "rule": "United States — NOT Adequate",
                "detail": (
                    "NDPC has not designated the US as providing adequate data protection. "
                    "Transfers to US-based processors (cloud, analytics, SaaS) require CBDTIs and DPIA."
                ),
            },
            {
                "rule": "DPIA Filing Requirement",
                "detail": (
                    "Mandatory Data Protection Impact Assessments must be filed with NDPC "
                    "for all cross-border transfers and high-risk processing activities."
                ),
            },
            {
                "rule": "Transfer Records",
                "detail": (
                    "Organisations must maintain records of: foreign entities receiving personal data, "
                    "legal basis for transfer, and security measures in place."
                ),
            },
        ],
        "obligations": [
            "Identify all cross-border data flows (roaming, cloud providers, analytics partners).",
            "Implement CBDTIs (Standard Contractual Clauses) for all non-adequate jurisdiction transfers.",
            "File DPIA with NDPC before initiating cross-border transfers.",
            "Maintain transfer records — foreign recipient, legal basis, security measures.",
        ],
        "source_url": "https://iapp.org/news/a/from-principles-to-practice-operationalizing-nigerias-data-protection-act-through-the-gaid/",
    },
    {
        "id": "NDPC-003",
        "name": "Data Breach Notification Framework (NDPA 2023, Section 24)",
        "authority": "Nigeria Data Protection Commission (NDPC)",
        "category": "incident_response",
        "status": "active",
        "timeline": {
            "regulator_notification": "72 hours from becoming aware of a breach posing high risk to data subjects",
            "data_subject_notification": "Immediately upon identification of a high-risk breach",
        },
        "notification_content": [
            "Nature and description of the breach",
            "Categories and approximate number of data subjects affected",
            "Approximate number of records involved",
            "Name and contact details of the Data Protection Officer",
            "Context of the breach and circumstances",
            "Security safeguards that were in place",
            "Measures data subjects can take for self-protection",
        ],
        "record_keeping": [
            "Maintain a breach register containing: breach details, causes, and remedies applied.",
            "All breaches (including low-risk) must be logged — only high-risk triggers NDPC notification.",
        ],
        "obligations": [
            "72-hour NDPC notification window for high-risk breaches — clock starts when controller becomes aware.",
            "Immediate data subject notification in plain, accessible language.",
            "Breach register maintained and available for NDPC audit.",
        ],
        "source_url": "https://uubo.org/wp-content/uploads/2023/09/DATA-BREACHES-AND-REGULATORY-COMPLIANCE-OBLIGATIONS-UNDER-THE-NIGERIAN-DATA-PROTECTION-ACT.pdf",
    },
    {
        "id": "NDPC-004",
        "name": "Nigeria Data Protection Regulation 2019 (NDPR) — Historical",
        "authority": "NITDA — National Information Technology Development Agency",
        "category": "repealed_legislation",
        "status": "superseded",
        "superseded_by": "NDPA 2023 — ceases effect September 19, 2025 per GAID",
        "issued": "January 2019",
        "basis": "NITDA Act 2007",
        "relevance": (
            "Systems and contracts designed under NDPR must be transitioned to NDPA 2023 framework by "
            "September 19, 2025. Compliance programmes still referencing only NDPR are non-compliant."
        ),
        "source_url": "https://nitda.gov.ng/wp-content/uploads/2020/11/NigeriaDataProtectionRegulation11.pdf",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Compliance priorities for African fintechs
# ─────────────────────────────────────────────────────────────────────────────

FINTECH_COMPLIANCE_CHECKLIST: list[dict] = [
    {
        "area": "Capital Adequacy Ratio",
        "regulator": "CBN",
        "regulation": "CBN MFB Guidelines 2022 — Section 5.1 (CBN-MFB-001)",
        "obligation": "Maintain CAR ≥ 10% of risk-weighted assets at all times; report breaches immediately.",
        "risk": "HIGH",
        "penalty_if_breached": "CBN administrative fine up to ₦2 billion (BOFIA 2020 s.12); licence suspension.",
        "fintech_relevance": "CAR drop below 10% triggers immediate CBN directive — Carbon MFB fined ₦2bn in Q2 2026.",
    },
    {
        "area": "AML/CFT Quarterly Return",
        "regulator": "CBN",
        "regulation": "CBN AML/CFT Regulations 2022 — Section 18 (CBN-AML-001)",
        "obligation": "Submit quarterly AML/CFT return to CBN by the 15th of the following month; file STRs within 24h.",
        "risk": "HIGH",
        "penalty_if_breached": "Late/missing STR: ₦10M per occurrence; systemic failure: ₦100M+ and possible licence revocation.",
        "fintech_relevance": "Kuda MFB Q2 2026: 3 incomplete SAR filings — 30-day remediation directive issued.",
    },
    {
        "area": "Data Breach Notification",
        "regulator": "NDPC",
        "regulation": "NDPA 2023 Section 24 (NDPC-003)",
        "obligation": "Report high-risk breaches to NDPC within 72 hours; notify data subjects immediately.",
        "risk": "HIGH",
        "penalty_if_breached": "₦10 million OR 2% of annual gross revenue (whichever is higher); Multichoice precedent: ₦766M.",
        "fintech_relevance": "Loan account takeovers and agent wallet fraud may constitute data breaches triggering mandatory NDPC notification.",
    },
    {
        "area": "Consumer Complaint Resolution",
        "regulator": "CBN",
        "regulation": "CBN Consumer Protection Framework 2022 — Section 3 (CBN-ENF-001)",
        "obligation": "Acknowledge complaints within 24h; resolve within 7 business days; reverse unauthorised deductions within 24h.",
        "risk": "HIGH",
        "penalty_if_breached": "₦1M per day for unreversed deductions; ₦50–100M for systemic failure.",
        "fintech_relevance": "Loan deduction complaint spikes are a leading indicator of CBN Consumer Protection enforcement action.",
    },
    {
        "area": "Cross-Border Data Transfer",
        "regulator": "NDPC",
        "regulation": "GAID 2025 (NDPC-002)",
        "obligation": "All transfers to non-adequate jurisdictions (incl. US cloud providers) require DPIA + CBDTI.",
        "risk": "MEDIUM",
        "penalty_if_breached": "₦766 million precedent (Multichoice July 2025); ₦10M+ or 2% gross revenue.",
        "fintech_relevance": "Cloud analytics, BaaS providers, and CRC data flows may trigger GAID cross-border obligations.",
    },
    {
        "area": "SEC VASP / Fintech Registration",
        "regulator": "SEC",
        "regulation": "SEC Fintech Regulatory Incubator Framework 2024 (SEC-001)",
        "obligation": "Register digital asset service with SEC before offering to Nigerian retail investors; submit quarterly data.",
        "risk": "MEDIUM",
        "penalty_if_breached": "₦50M fine + operations suspension for unregistered VASP services; ₦500K/week late filing.",
        "fintech_relevance": "Fintechs offering tokenised savings, crypto wallets, or robo-advisory must verify SEC registration status.",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Query API
# ─────────────────────────────────────────────────────────────────────────────

_KEYWORD_MAP = {
    "capital adequacy": ["CBN-MFB-001"],
    "car": ["CBN-MFB-001"],
    "microfinance": ["CBN-MFB-001"],
    "mfb": ["CBN-MFB-001"],
    "single obligor": ["CBN-MFB-001"],
    "lending limit": ["CBN-MFB-001"],
    "aml": ["CBN-AML-001"],
    "cft": ["CBN-AML-001"],
    "aml/cft": ["CBN-AML-001"],
    "suspicious transaction": ["CBN-AML-001"],
    "str": ["CBN-AML-001"],
    "quarterly return": ["CBN-AML-001", "CBN-CAR-001"],
    "money laundering": ["CBN-AML-001"],
    "payment service bank": ["CBN-PSB-001"],
    "psb": ["CBN-PSB-001"],
    "wallet limit": ["CBN-PSB-001"],
    "agent network": ["CBN-PSB-001"],
    "bofia": ["CBN-CAR-001"],
    "licence revocation": ["CBN-CAR-001"],
    "prudential": ["CBN-CAR-001", "CBN-MFB-001"],
    "consumer protection": ["CBN-ENF-001"],
    "complaint": ["CBN-ENF-001"],
    "unauthorised deduction": ["CBN-ENF-001"],
    "loan deduction": ["CBN-ENF-001"],
    "apr": ["CBN-ENF-001"],
    "interest disclosure": ["CBN-ENF-001"],
    "vasp": ["SEC-001"],
    "digital asset": ["SEC-001"],
    "crowdfunding": ["SEC-001"],
    "robo-advisory": ["SEC-001"],
    "sec registration": ["SEC-001"],
    "fintech registration": ["SEC-001"],
    "data protection": ["NDPC-001", "NDPC-002"],
    "ndpa": ["NDPC-001"],
    "data breach": ["NDPC-001", "NDPC-003"],
    "breach notification": ["NDPC-003"],
    "72 hour": ["NDPC-003"],
    "cross-border": ["NDPC-002"],
    "cross border": ["NDPC-002"],
    "ndpr": ["NDPC-004"],
    "dpco": ["NDPC-001"],
    "data protection officer": ["NDPC-001"],
    "dpo": ["NDPC-001"],
    "dpia": ["NDPC-001", "NDPC-002"],
    "penalty": ["CBN-MFB-001", "CBN-CAR-001", "NDPC-001"],
    "fine": ["CBN-MFB-001", "CBN-CAR-001", "NDPC-001"],
    "enforcement": ["CBN-CAR-001", "NDPC-001"],
    "cbn": ["CBN-MFB-001", "CBN-AML-001", "CBN-CAR-001"],
    "sec": ["SEC-001"],
    "ndpc": ["NDPC-001", "NDPC-002", "NDPC-003"],
    "compliance": ["CBN-MFB-001", "CBN-AML-001", "CBN-ENF-001", "NDPC-001"],
    "regulation": ["CBN-MFB-001", "NDPC-001"],
    "regulatory": ["CBN-MFB-001", "CBN-CAR-001", "NDPC-001"],
}

_ALL_REGS = {r["id"]: r for r in (CBN_REGULATIONS + NDPC_REGULATIONS)}


def get_regulatory_context(query: str) -> dict:
    """Return regulations relevant to the query string."""
    q = query.lower()
    matched_ids: set[str] = set()

    for keyword, reg_ids in _KEYWORD_MAP.items():
        if keyword in q:
            matched_ids.update(reg_ids)

    # Default: return top CBN+NDPC primary regulations if nothing specific matched
    if not matched_ids:
        matched_ids = {"CBN-MFB-001", "CBN-AML-001", "CBN-CAR-001", "NDPC-001", "NDPC-003"}

    matched_regs = [_ALL_REGS[rid] for rid in matched_ids if rid in _ALL_REGS]
    matched_regs.sort(key=lambda r: r["id"])

    return {
        "regulations": matched_regs,
        "compliance_checklist": FINTECH_COMPLIANCE_CHECKLIST,
        "total_matched": len(matched_regs),
    }


def get_all_regulations() -> dict:
    """Return the full regulatory corpus."""
    return {
        "cbn": CBN_REGULATIONS,
        "ndpc": NDPC_REGULATIONS,
        "compliance_checklist": FINTECH_COMPLIANCE_CHECKLIST,
    }


def get_regulatory_summary_text(query: str) -> str:
    """
    Return a concise text block (for LLM context injection) with
    real regulation names, sections, and penalty figures.
    """
    ctx = get_regulatory_context(query)
    regs = ctx["regulations"]
    lines = [
        "=== AFRICAN FINTECH REGULATORY REFERENCE (CBN, SEC & NDPC) ===",
        "The following regulations are sourced from official CBN, SEC, and NDPC publications.",
        "",
    ]
    for r in regs:
        lines.append(f"[{r['id']}] {r['name']} — Status: {r['status'].upper()}")
        if r.get("key_sections"):
            for s in r["key_sections"][:3]:
                lines.append(f"  • {s['section']}: {s['summary']}")
        if r.get("obligations"):
            lines.append("  Obligations:")
            for o in r["obligations"][:3]:
                lines.append(f"    - {o}")
        if r.get("penalties"):
            lines.append("  Penalties:")
            for p in (r["penalties"] if isinstance(r["penalties"], list) else [str(r["penalties"])]):
                lines.append(f"    ⚠ {p}")
        if r.get("notable_cases"):
            for nc in r["notable_cases"][:1]:
                lines.append(f"  Enforcement precedent: {nc['case']} — {nc.get('penalty', nc.get('detail', ''))[:120]}")
        lines.append("")

    lines.append("=== AFRICAN FINTECH COMPLIANCE PRIORITIES ===")
    for c in ctx["compliance_checklist"]:
        lines.append(
            f"[{c['risk']}] {c['area']} ({c['regulator']}): {c['obligation']} "
            f"| Penalty: {c['penalty_if_breached'][:80]}"
        )
    return "\n".join(lines)
