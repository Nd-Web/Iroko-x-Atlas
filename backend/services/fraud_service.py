"""
Fraud Intelligence Service
===========================
Demo fraud signal data for a large telecom operator covering:
  - Procurement / invoice fraud
  - SIM-swap account takeover
  - Mobile-money (MoMo) agent collusion fraud
  - Interconnect bypass and regulatory-compliance gaps

In production these signals would be sourced from:
  CDR/transaction monitoring systems, ERP/AP systems, MoMo platform logs,
  and AI-powered document corpus analysis.
"""

FRAUD_SIGNALS = [
    {
        "id": "FRD-001",
        "category": "procurement",
        "risk": "HIGH",
        "title": "Duplicate Invoice — Zumax Telecoms",
        "detail": (
            "Invoice #INV-2025-0441 for microwave backhaul spares submitted twice (₦4.2M each) by Zumax Telecoms in Q4 2025. "
            "Second submission made 6 days after the first via a different AP vendor code. "
            "Payment of ₦4.2M was already processed before the duplicate was flagged."
        ),
        "region": None,
        "amount_ngn": 4_200_000,
        "detected_at": "2026-02-14T09:30:00Z",
        "status": "under_review",
        "doc_ref": "PROC-INV-Q4-2025-0441",
    },
    {
        "id": "FRD-002",
        "category": "account_takeover",
        "risk": "HIGH",
        "title": "SIM-Swap Fraud Spike — Kano Region",
        "detail": (
            "SIM-swap requests in Kano surged 340% above the 30-day average. "
            "1,247 suspicious swap attempts recorded in a 72-hour window (2026-02-28 to 2026-03-02). "
            "84% initiated through 4 dealer codes: KN-AG-0023, KN-AG-0091, KN-AG-0147, KN-AG-0203. "
            "Pattern matches SIM-swap account takeover preceding MoMo wallet withdrawals and OTP interception."
        ),
        "region": "Kano",
        "amount_ngn": None,
        "detected_at": "2026-03-01T14:00:00Z",
        "status": "escalated",
        "doc_ref": "SIM-KN-SWAPSPIKE-2026-03",
    },
    {
        "id": "FRD-003",
        "category": "procurement",
        "risk": "MEDIUM",
        "title": "Vendor Concentration — Optimus Links Nigeria",
        "detail": (
            "73% of Q1 2026 passive-infrastructure procurement (₦287M total) awarded to Optimus Links Nigeria Ltd. "
            "Vendor was registered 6 months before its first contract. "
            "No competitive tender for any contract above ₦50M, contrary to procurement policy. "
            "Company directors overlap with a former network rollout manager (resigned Nov 2025)."
        ),
        "region": None,
        "amount_ngn": 287_000_000,
        "detected_at": "2026-02-28T10:00:00Z",
        "status": "flagged",
        "doc_ref": "PROC-Q1-2026-ANTENNA",
    },
    {
        "id": "FRD-004",
        "category": "agent_fraud",
        "risk": "HIGH",
        "title": "MoMo Agent Reversal Pattern — Lagos",
        "detail": (
            "847 MoMo agent transaction reversals detected in Lagos in a 24-hour window (2026-04-12). "
            "92% originated from 3 agent codes: LG-AG-1144, LG-AG-2201, LG-AG-3007. "
            "Total value reversed: ₦31.4M. These agents had a 94% reversal rate vs 0.3% network average. "
            "Pattern matches known agent-collusion fraud: agents initiate and immediately reverse transactions "
            "to farm commissions. Correlates with the Q1 2026 MoMo deduction complaints spike (₦28.4M disputed)."
        ),
        "region": "Lagos",
        "amount_ngn": 31_400_000,
        "detected_at": "2026-04-12T23:45:00Z",
        "status": "escalated",
        "doc_ref": "MOMO-LG-REV-2026-04-12",
    },
    {
        "id": "FRD-005",
        "category": "procurement",
        "risk": "MEDIUM",
        "title": "Round-Number Billing — GlobalTech Services",
        "detail": (
            "14 consecutive invoices from GlobalTech Services Ltd total exactly ₦500,000 or ₦1,000,000. "
            "Statistical probability of natural occurrence: <0.3%. "
            "Consistent with invoice splitting to remain below the ₦2M threshold requiring CFO approval. "
            "Total billed Q1 2026: ₦8.5M across 14 transactions."
        ),
        "region": None,
        "amount_ngn": 8_500_000,
        "detected_at": "2026-03-15T11:00:00Z",
        "status": "under_review",
        "doc_ref": "FIN-GLOBALTECH-Q1-2026",
    },
    {
        "id": "FRD-006",
        "category": "compliance",
        "risk": "MEDIUM",
        "title": "Interconnect Bypass (SIM-Box) Indicators — Lagos & Ogun",
        "detail": (
            "CDR analysis flagged 14 gateway traffic patterns consistent with SIM-box interconnect bypass: "
            "international voice traffic terminating as local calls through high-usage SIM clusters "
            "with no data usage, static cell IDs, and near-continuous call activity. "
            "None of the 14 patterns were escalated to the revenue-assurance register as required by internal policy. "
            "Interconnect bypass deprives the operator of international termination revenue and breaches "
            "NCC licensing conditions; the NCC has directed operators to actively detect and disable SIM-box lines. "
            "If verified, this gap could trigger an NCC compliance inquiry alongside the ongoing revenue leakage."
        ),
        "region": "Lagos / Ogun",
        "amount_ngn": None,
        "detected_at": "2026-01-20T08:00:00Z",
        "status": "under_review",
        "doc_ref": "RA-SIMBOX-Q1-2026-CDR",
        "regulation_refs": [
            "Nigerian Communications Act 2003 — licence-condition enforcement powers",
            "NCC directives on SIM-box detection and disconnection",
            "Internal Revenue Assurance Policy — 24-hour escalation of bypass indicators",
        ],
    },
    {
        "id": "FRD-007",
        "category": "compliance",
        "risk": "HIGH",
        "title": "NDPA 2023 Data Breach Notification Gap — SIM-Swap & MoMo Events",
        "detail": (
            "The SIM-swap surge in Kano (FRD-002) and MoMo agent reversal pattern in Lagos (FRD-004) both involve "
            "unauthorised access to subscriber accounts — meeting the NDPA 2023 definition of a personal data breach. "
            "Nigeria Data Protection Act 2023 Section 24 requires notification to the NDPC within 72 hours of "
            "becoming aware of a breach posing high risk to data subjects' rights. "
            "Data subjects (affected subscribers) must be notified immediately in plain language. "
            "Large operators (>₦1bn revenue) are classified as Data Controllers of Major Importance — penalty exposure is "
            "₦10 million OR 2% of annual gross revenue (whichever is higher). "
            "Enforcement precedent: Fidelity Bank fined ₦555.8 million by NDPC in 2024 for data infractions. "
            "Multichoice Nigeria fined ₦766.2 million by NDPC in July 2025 for illegal cross-border data transfer. "
            "Immediate action required: NDPC breach notification and subscriber alert if 72-hour window not yet elapsed."
        ),
        "region": "Kano / Lagos",
        "amount_ngn": None,
        "detected_at": "2026-04-13T06:00:00Z",
        "status": "escalated",
        "doc_ref": "NDPC-BREACH-2026-04",
        "regulation_refs": [
            "NDPA 2023 Section 24 — 72-hour breach notification to NDPC",
            "NDPA 2023 Section 48 — ₦10M or 2% gross revenue penalty for major importance controllers",
            "GAID 2025 — cross-border data transfer restrictions effective September 19, 2025",
            "Fidelity Bank precedent — ₦555.8M NDPC fine (2024)",
        ],
    },
]

_RISK_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def get_fraud_signals(
    category: str | None = None,
    risk: str | None = None,
    region: str | None = None,
) -> list:
    signals = FRAUD_SIGNALS
    if category:
        signals = [s for s in signals if s["category"] == category]
    if risk:
        signals = [s for s in signals if s["risk"] == risk.upper()]
    if region:
        signals = [s for s in signals if s.get("region") and s["region"].lower() == region.lower()]
    return sorted(signals, key=lambda s: _RISK_ORDER.get(s["risk"], 99))


def get_fraud_summary() -> dict:
    high   = [s for s in FRAUD_SIGNALS if s["risk"] == "HIGH"]
    medium = [s for s in FRAUD_SIGNALS if s["risk"] == "MEDIUM"]
    low    = [s for s in FRAUD_SIGNALS if s["risk"] == "LOW"]

    total_exposure = sum(s["amount_ngn"] for s in FRAUD_SIGNALS if s["amount_ngn"])

    by_category: dict = {}
    for s in FRAUD_SIGNALS:
        cat = s["category"]
        if cat not in by_category:
            by_category[cat] = {"count": 0, "high_count": 0, "exposure_ngn": 0}
        by_category[cat]["count"] += 1
        if s["risk"] == "HIGH":
            by_category[cat]["high_count"] += 1
        if s["amount_ngn"]:
            by_category[cat]["exposure_ngn"] += s["amount_ngn"]

    return {
        "total_signals":      len(FRAUD_SIGNALS),
        "high_risk":          len(high),
        "medium_risk":        len(medium),
        "low_risk":           len(low),
        "total_exposure_ngn": total_exposure,
        "by_category":        by_category,
        "signals":            sorted(FRAUD_SIGNALS, key=lambda s: _RISK_ORDER.get(s["risk"], 99)),
    }
