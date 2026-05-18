"""
Regulatory Service — NCC & NDPC Compliance Reference Corpus
=============================================================
Comprehensive, citable regulatory knowledge base for MTN Nigeria.

Sources (all verified, 2023–2025):
  NCC  — Nigerian Communications Commission (ncc.gov.ng)
  NDPC — Nigeria Data Protection Commission (ndpc.gov.ng)

Penalty precedents, section references, and enforcement actions are real.
This corpus is injected into the AI's context window for regulatory queries
and surfaces in the compliance tab of the Fraud/Compliance panel.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# NCC Regulatory Corpus
# ─────────────────────────────────────────────────────────────────────────────

NCC_REGULATIONS: list[dict] = [
    {
        "id": "NCC-001",
        "name": "Nigerian Communications Act 2003 (NCA 2003)",
        "authority": "National Assembly — Act No. 19 of 2003",
        "category": "primary_legislation",
        "status": "active",
        "key_sections": [
            {
                "section": "Section 3",
                "summary": "Establishes the Nigerian Communications Commission and its full regulatory authority over the sector.",
            },
            {
                "section": "Section 70",
                "summary": (
                    "Empowers NCC to make and publish regulations covering: written authorisations, "
                    "spectrum/number assignment, offences and penalties, fees and charges, and Quality of Service standards."
                ),
            },
            {
                "section": "Section 73",
                "summary": (
                    "Prohibition on submitting false or misleading information to the NCC. "
                    "Constitutes a regulatory offence subject to administrative sanction and potential criminal prosecution."
                ),
            },
        ],
        "obligations": [
            "All telecommunications services require NCC licence before operation.",
            "Licensees must submit accurate periodic reports to the NCC.",
            "False or misleading submissions to NCC constitute an offence under s.73.",
        ],
        "penalties": [
            "Unlicensed operations: fine of 1×–10× initial licence fee + imprisonment ≤1 year, or both; equipment forfeiture.",
            "False information submission: fine up to ₦100,000 or imprisonment.",
            "NCC retains authority for further enforcement beyond initial fine payment.",
        ],
        "notable_cases": [
            {
                "case": "MTN Nigeria SIM Registration Fine (2015–2019)",
                "detail": (
                    "MTN failed to disconnect 5.2 million improperly-registered SIM lines under "
                    "NCC Telephone Subscribers Registration Regulations 2011. "
                    "Initial NCC fine: ₦1.04 trillion (October 20, 2015) at ₦200,000 per unregistered SIM. "
                    "Negotiated down to ₦330 billion. MTN paid ₦275 billion upfront, balance in six tranches, "
                    "plus ₦50 billion 'goodwill' payment. Total settlement: ~₦330 billion."
                ),
            }
        ],
        "source_url": "https://ncc.gov.ng/sites/default/files/2024-12/Legislation-Nigerian_Communications_Act_2003.pdf",
    },
    {
        "id": "NCC-002",
        "name": "Consumer Code of Practice Regulations 2024",
        "authority": "NCC Consumer Affairs Bureau",
        "category": "consumer_protection",
        "status": "active",
        "supersedes": "Consumer Code of Practice Regulations 2007 and 2018",
        "key_sections": [
            {
                "section": "General Code — Billing",
                "summary": "Licensees must provide itemised billing details with required notice periods for changes.",
            },
            {
                "section": "Emergency Services",
                "summary": "Emergency service calls must be provided free of charge at all times.",
            },
            {
                "section": "Complaint Management",
                "summary": (
                    "Mandatory complaint recording systems with categorised tracking for recurring problem identification. "
                    "Each licensee must maintain an Individual Consumer Code of Practice (ICCP) aligned with the General Code."
                ),
            },
            {
                "section": "Network Outage Notification",
                "summary": (
                    "Operators must promptly inform consumers of major outages via media channels, disclosing "
                    "the cause, affected areas, and restoration timeline. Planned outages require one-week advance notice."
                ),
            },
        ],
        "obligations": [
            "Maintain and publish Individual Consumer Code of Practice (ICCP).",
            "Free emergency service calls.",
            "Itemised billing available on request.",
            "Complaint tracking and escalation system with defined resolution timelines.",
            "Proactive outage communication — 7-day notice for planned, immediate notice for unplanned.",
        ],
        "penalties": [
            "Administrative fines per Second Schedule of Enforcement Regulations.",
            "Licence suspension or revocation for persistent non-compliance.",
        ],
        "source_url": "https://ncc.gov.ng/sites/default/files/2024-11/Legal_Regulations_Consumer_Code_of_Practice_Regulations_2024.pdf",
    },
    {
        "id": "NCC-003",
        "name": "Quality of Service (QoS) Business Rules 2024",
        "authority": "NCC — Nigerian Communications Commission",
        "category": "network_performance",
        "status": "active",
        "key_kpis": [
            {"metric": "Dropped Call Rate (DCR)", "threshold": "Operator-specific targets by network generation (2G/3G/4G)"},
            {"metric": "Call Setup Success Rate (CSSR)", "threshold": "Network segment-specific targets"},
            {"metric": "Mean Time To Repair (MTTR)", "threshold": "≤ 2.5 hours for hub and terminal sites"},
            {"metric": "Traffic Congestion", "threshold": "Defined limits per network technology"},
        ],
        "reporting": {
            "frequency": "Quarterly",
            "deadline": "15th of the first month of each quarter",
            "submission": "NCC Abuja headquarters",
            "scope": "All network segments — 2G, 3G, 4G",
        },
        "obligations": [
            "Submit quarterly QoS reports by the 15th of the first month of each quarter.",
            "Maintain MTTR ≤ 2.5 hours for hub and terminal sites.",
            "Comply with DCR, CSSR, and congestion thresholds per NCC-specified technology standards.",
            "QoS data submitted must match internal OMC-R records — mismatches constitute misrepresentation (NCA 2003 s.73).",
        ],
        "penalties": [
            "Administrative fines per Second Schedule — estimated ₦12.4 billion sector-wide enforcement (2024).",
            "Persistent QoS failures can trigger licence review.",
        ],
        "source_url": "https://ncc.gov.ng/sites/default/files/2024-11/Legal_Business_Rules_Quality_of_Service_(QoS)_Business_Rules_2024.pdf",
    },
    {
        "id": "NCC-004",
        "name": "Business Rules for SIM Registration 2025",
        "authority": "NCC — Nigerian Communications Commission",
        "category": "subscriber_management",
        "status": "active",
        "supersedes": "NCC Telephone Subscribers Registration Regulations 2011",
        "key_provisions": [
            {
                "rule": "NIN Requirement",
                "detail": (
                    "National Identification Number (NIN) mandatory for all new SIM registrations. "
                    "Foreigners resident ≥2 years require NIN for SIM registration and MNP. "
                    "Foreigners in transit or employed <24 months are exempt."
                ),
            },
            {
                "rule": "Revenue Generating Event (RGE)",
                "detail": (
                    "Every activated line must trigger a Revenue Generating Event within 48 hours. "
                    "Second RGE required by the 96-hour mark. Non-compliance = unregistered SIM liability."
                ),
            },
            {
                "rule": "Activation Limits",
                "detail": "CSPs must enforce NCC-specified per-subscriber activation limits.",
            },
        ],
        "obligations": [
            "All new SIM activations must be linked to a valid NIN.",
            "Revenue Generating Events must occur within 48 and 96 hours of activation.",
            "Unregistered or improperly-registered SIMs must be disconnected within NCC-prescribed timeframes.",
            "Subscriber data retention subject to NDPA 2023.",
        ],
        "penalties": [
            "₦200,000 per unregistered SIM (precedent: MTN 2015 fine).",
            "Cumulative liability can reach ₦1+ trillion for systemic non-compliance.",
        ],
        "source_url": "https://www.ncc.gov.ng/sites/default/files/2025-07/Business-Rules-for-the-Registration-of-Communications-Subscribers-Regulations-2025.pdf",
    },
    {
        "id": "NCC-005",
        "name": "Frequency Spectrum (Fees and Pricing) Regulations 2021",
        "authority": "NCC — Section 70, NCA 2003",
        "category": "spectrum_management",
        "status": "active",
        "licence_types": [
            {"type": "Short-term permit", "tenure": "4 months"},
            {"type": "Medium-term permit", "tenure": "1 year"},
            {"type": "Long-term licence", "tenure": "5, 10, or 15 years"},
        ],
        "obligations": [
            "All spectrum must be licenced before use.",
            "Fees payable per Regulations schedule; non-payment triggers suspension.",
            "Signal boosters require prior NCC authorisation — unauthorised installation is a regulatory offence.",
        ],
        "penalties": [
            "Unauthorised spectrum use: criminal prosecution and equipment forfeiture.",
            "Unauthorised signal booster installation: sanctions and prosecution.",
        ],
        "source_url": "https://ncc.gov.ng/media/138/download",
    },
    {
        "id": "NCC-006",
        "name": "Guidelines on Corporate Governance for Telecommunications 2024",
        "authority": "NCC",
        "category": "corporate_governance",
        "status": "active",
        "effective_date": "March 1, 2025",
        "supersedes": "Code of Corporate Governance for Telecommunications Industry 2016",
        "key_provisions": [
            "Directors limited to maximum two terms of five years (10 years total).",
            "Independent Non-Executive Directors: maximum two terms of four years (8 years total).",
            "Mandatory three-year cooling-off period before reappointment.",
            "At least one Non-Executive Director and one Independent Director must have ICT/cybersecurity expertise.",
        ],
        "obligations": [
            "Comply with board composition and tenure requirements by March 1, 2025.",
            "Submit annual corporate governance compliance reports to NCC.",
        ],
        "penalties": [
            "Non-compliance can result in licence suspension or revocation.",
        ],
        "source_url": "https://www.ncc.gov.ng/sites/default/files/2025-07/Guidelines-on-Corporate-Gov.pdf",
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
        "obligations_for_mtn": [
            "Classify MTN as a Data Controller of Major Importance — penalty exposure up to 2% annual gross revenue.",
            "Subscriber data (PII, call records, biometrics for SIM registration) subject to NDPA 2023.",
            "SIM registration data retention aligned with NCC SIM Business Rules 2025 AND NDPA 2023.",
            "Cross-border data transfer (e.g. roaming partners, cloud providers) requires DPIA and NDPC filing.",
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
# Compliance obligations specifically for MTN Nigeria
# ─────────────────────────────────────────────────────────────────────────────

MTN_COMPLIANCE_CHECKLIST: list[dict] = [
    {
        "area": "QoS Reporting",
        "regulator": "NCC",
        "regulation": "QoS Business Rules 2024 (NCC-003)",
        "obligation": "Submit quarterly QoS report by the 15th of the first month of each quarter.",
        "risk": "HIGH",
        "penalty_if_breached": "Administrative fine (estimated ₦12.4 billion sector-wide enforcement); licence review.",
        "mtn_relevance": "NCC QoS submission must match OMC-R internal records — any discrepancy violates NCA 2003 s.73.",
    },
    {
        "area": "SIM Registration & NIN Compliance",
        "regulator": "NCC",
        "regulation": "SIM Registration Business Rules 2025 (NCC-004)",
        "obligation": "All SIM activations linked to valid NIN; RGE within 48h and 96h of activation.",
        "risk": "HIGH",
        "penalty_if_breached": "₦200,000 per non-compliant SIM — systemic failure = ₦1+ trillion exposure (MTN 2015 precedent).",
        "mtn_relevance": "SIM swap fraud (FRD-002) combined with registration non-compliance creates compounding regulatory liability.",
    },
    {
        "area": "Data Breach Notification",
        "regulator": "NDPC",
        "regulation": "NDPA 2023 Section 24 (NDPC-003)",
        "obligation": "Report high-risk breaches to NDPC within 72 hours; notify data subjects immediately.",
        "risk": "HIGH",
        "penalty_if_breached": "₦10 million OR 2% of annual gross revenue (MTN Nigeria gross revenue FY2025: ₦5.203 trillion → max penalty ≈ ₦104 billion).",
        "mtn_relevance": "SIM swap account takeovers and MoMo fraud may constitute data breaches triggering mandatory NDPC notification.",
    },
    {
        "area": "Cross-Border Data Transfer",
        "regulator": "NDPC",
        "regulation": "GAID 2025 (NDPC-002)",
        "obligation": "All transfers to non-adequate jurisdictions (incl. US cloud providers) require DPIA + CBDTI.",
        "risk": "MEDIUM",
        "penalty_if_breached": "₦766 million precedent (Multichoice July 2025); ₦10M+ or 2% gross revenue.",
        "mtn_relevance": "Analytics platforms, roaming clearing houses, and foreign cloud providers may trigger GAID obligations.",
    },
    {
        "area": "Consumer Code Compliance",
        "regulator": "NCC",
        "regulation": "Consumer Code of Practice Regulations 2024 (NCC-002)",
        "obligation": "Maintain ICCP; proactive outage notification; itemised billing; complaint resolution SLAs.",
        "risk": "MEDIUM",
        "penalty_if_breached": "Administrative fine; licence suspension for persistent breach.",
        "mtn_relevance": "NPS/CSAT degradation and unresolved complaint backlogs are early warning indicators of CCOP breach.",
    },
    {
        "area": "Corporate Governance",
        "regulator": "NCC",
        "regulation": "Guidelines on Corporate Governance 2024 (NCC-006)",
        "obligation": "Director tenure limits; cooling-off periods; ICT/cybersecurity expertise on board.",
        "risk": "MEDIUM",
        "penalty_if_breached": "Licence suspension or revocation.",
        "mtn_relevance": "Board composition must be audited against new guidelines effective March 1, 2025.",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Query API
# ─────────────────────────────────────────────────────────────────────────────

_KEYWORD_MAP = {
    "qos": ["NCC-003"],
    "quality of service": ["NCC-003"],
    "dropped call": ["NCC-003"],
    "mttr": ["NCC-003"],
    "network availability": ["NCC-003"],
    "sim": ["NCC-004"],
    "sim swap": ["NCC-004"],
    "nin": ["NCC-004"],
    "sim registration": ["NCC-004"],
    "spectrum": ["NCC-005"],
    "signal booster": ["NCC-005"],
    "consumer code": ["NCC-002"],
    "complaint": ["NCC-002"],
    "outage notification": ["NCC-002"],
    "billing": ["NCC-002"],
    "corporate governance": ["NCC-006"],
    "board": ["NCC-006"],
    "nca": ["NCC-001"],
    "nigerian communications act": ["NCC-001"],
    "misrepresentation": ["NCC-001", "NCC-003"],
    "false submission": ["NCC-001", "NCC-003"],
    "data protection": ["NDPC-001", "NDPC-002"],
    "ndpa": ["NDPC-001"],
    "data breach": ["NDPC-001", "NDPC-003"],
    "breach notification": ["NDPC-003"],
    "72 hour": ["NDPC-003"],
    "cross-border": ["NDPC-002"],
    "cross border": ["NDPC-002"],
    "gdpr": ["NDPC-001", "NDPC-004"],
    "ndpr": ["NDPC-004"],
    "dpco": ["NDPC-001"],
    "data protection officer": ["NDPC-001"],
    "dpo": ["NDPC-001"],
    "dpia": ["NDPC-001", "NDPC-002"],
    "penalty": ["NCC-001", "NDPC-001"],
    "fine": ["NCC-001", "NDPC-001"],
    "enforcement": ["NCC-001", "NDPC-001"],
    "ncc": ["NCC-001", "NCC-002", "NCC-003"],
    "ndpc": ["NDPC-001", "NDPC-002", "NDPC-003"],
    "compliance": ["NCC-001", "NCC-002", "NCC-003", "NDPC-001"],
    "regulation": ["NCC-001", "NDPC-001"],
    "regulatory": ["NCC-001", "NDPC-001"],
}

_ALL_REGS = {r["id"]: r for r in (NCC_REGULATIONS + NDPC_REGULATIONS)}


def get_regulatory_context(query: str) -> dict:
    """
    Return regulations relevant to the query string.
    Always includes the compliance checklist for MTN.
    """
    q = query.lower()
    matched_ids: set[str] = set()

    for keyword, reg_ids in _KEYWORD_MAP.items():
        if keyword in q:
            matched_ids.update(reg_ids)

    # Default: return top NCC+NDPC primary legislation if nothing specific matched
    if not matched_ids:
        matched_ids = {"NCC-001", "NCC-002", "NCC-003", "NDPC-001", "NDPC-003"}

    matched_regs = [_ALL_REGS[rid] for rid in matched_ids if rid in _ALL_REGS]
    matched_regs.sort(key=lambda r: r["id"])

    return {
        "regulations": matched_regs,
        "compliance_checklist": MTN_COMPLIANCE_CHECKLIST,
        "total_matched": len(matched_regs),
    }


def get_all_regulations() -> dict:
    """Return the full regulatory corpus."""
    return {
        "ncc": NCC_REGULATIONS,
        "ndpc": NDPC_REGULATIONS,
        "compliance_checklist": MTN_COMPLIANCE_CHECKLIST,
    }


def get_regulatory_summary_text(query: str) -> str:
    """
    Return a concise text block (for LLM context injection) with
    real regulation names, sections, and penalty figures.
    """
    ctx = get_regulatory_context(query)
    regs = ctx["regulations"]
    lines = [
        "=== NIGERIAN REGULATORY REFERENCE (NCC & NDPC) ===",
        "The following regulations are sourced from official NCC and NDPC publications.",
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

    lines.append("=== MTN NIGERIA COMPLIANCE PRIORITIES ===")
    for c in ctx["compliance_checklist"]:
        lines.append(
            f"[{c['risk']}] {c['area']} ({c['regulator']}): {c['obligation']} "
            f"| Penalty: {c['penalty_if_breached'][:80]}"
        )
    return "\n".join(lines)
