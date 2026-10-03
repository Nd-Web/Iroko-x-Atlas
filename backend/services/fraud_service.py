"""
Fraud Intelligence Service
===========================
Compatibility interface for fraud monitoring. The former sample signals have
been retired. Real monitoring integrations are required before reporting activity.
"""

FRAUD_SIGNALS: list[dict] = []  # Real monitoring evidence is required.

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
