"""
services/regulatory_returns/prudential.py

Monthly prudential computations for an MFB: statement of financial position
(MMFBR 300) and year-to-date profit or loss (MMFBR 1000) totals, the
prudential ratios, loan classification and provisioning, and single-obligor /
insider exposure tests. Pure functions — no I/O — so every figure in a
generated return is reproducible from its inputs.

Limits applied (Revised Regulatory and Supervisory Guidelines for MFBs and the
CBN Prudential Guidelines for MFBs):
  capital adequacy ratio            >= 10%
  liquidity ratio                   >= 20% of deposit liabilities
  fixed assets                      <= 20% of shareholders' funds unimpaired by losses
  single obligor — individual       <= 1% of shareholders' funds
  single obligor — group/coop/corp. <= 5% of shareholders' funds
  aggregate insider-related credit  <= 5% of shareholders' funds
  loan classification (days past due) and provision:
    performing 0–30 (1%), pass & watch 31–59 (5%), substandard 60–90 (20%),
    doubtful 91–180 (50%), lost > 180 (100%)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .catalog import LICENCE_CATEGORIES, MINIMUM_CAPITAL

# ─── Line items ───────────────────────────────────────────────────────────────
# (code, label, group). Groups drive totals and ratio inputs.

SFP_LINES: tuple[tuple[str, str, str], ...] = (
    ("A01", "Cash in vault", "liquid0"),
    ("A02", "Balances with the Central Bank of Nigeria", "liquid0"),
    ("A03", "Balances with other banks and OFIs", "liquid20"),
    ("A04", "Placements with banks and OFIs (maturing within 90 days)", "liquid20"),
    ("A05", "Treasury bills and other FGN securities", "liquid0"),
    ("A06", "Other investment securities and longer-dated placements", "asset"),
    ("A07", "Loans and advances to customers — gross", "loans_gross"),
    ("A08", "Less: impairment allowance on loans and advances", "loans_impairment"),
    ("A09", "Investment in subsidiaries and associates", "asset"),
    ("A10", "Other assets", "asset"),
    ("A11", "Property, plant and equipment (net)", "ppe"),
    ("A12", "Intangible assets", "intangible"),
    ("A13", "Deferred tax assets", "asset"),
    ("L01", "Demand deposits", "deposit"),
    ("L02", "Savings deposits", "deposit"),
    ("L03", "Time / term deposits", "deposit"),
    ("L04", "Other deposits (incl. mandatory savings and cash collateral)", "deposit"),
    ("L05", "Takings and borrowings from banks and OFIs", "liability"),
    ("L06", "On-lending facilities and other borrowings (incl. CBN intervention funds)", "liability"),
    ("L07", "Current income tax payable", "liability"),
    ("L08", "Deferred tax liabilities", "liability"),
    ("L09", "Other liabilities", "liability"),
    ("E01", "Paid-up share capital", "equity"),
    ("E02", "Share premium", "equity"),
    ("E03", "Statutory reserve", "equity"),
    ("E04", "Regulatory risk reserve", "equity"),
    ("E05", "Retained earnings / (accumulated losses)", "equity"),
    ("E06", "Other reserves", "equity"),
)

PL_LINES: tuple[tuple[str, str, str], ...] = (
    ("I01", "Interest income — loans and advances", "interest_income"),
    ("I02", "Interest income — placements and investment securities", "interest_income"),
    ("X01", "Interest expense — deposits", "interest_expense"),
    ("X02", "Interest expense — borrowings", "interest_expense"),
    ("I03", "Fee and commission income", "other_income"),
    ("I04", "Other operating income", "other_income"),
    ("X03", "Impairment charge on loans and other assets", "impairment"),
    ("X04", "Staff costs", "opex"),
    ("X05", "Depreciation and amortisation", "opex"),
    ("X06", "Other operating expenses", "opex"),
    ("X07", "Income tax expense", "tax"),
)

# Lines that may legitimately be negative.
SIGNED_LINES = {"E05", "E06", "I04"}

LIMITS = {
    "car_min": 0.10,
    "liquidity_min": 0.20,
    "fixed_assets_max": 0.20,
    "single_obligor_individual": 0.01,
    "single_obligor_other": 0.05,
    "insider_aggregate": 0.05,
}

# Risk weights used when the bank does not supply its own RWA figure.
RISK_WEIGHTS = {"liquid0": 0.0, "liquid20": 0.20, "asset": 1.0, "loans_net": 1.0, "ppe": 1.0}

LOAN_CLASSES: tuple[tuple[str, int, int | None, float], ...] = (
    # (class, min DPD, max DPD inclusive or None, provision rate)
    ("Performing", 0, 30, 0.01),
    ("Pass & watch", 31, 59, 0.05),
    ("Substandard", 60, 90, 0.20),
    ("Doubtful", 91, 180, 0.50),
    ("Lost", 181, None, 1.00),
)
NON_PERFORMING = {"Substandard", "Doubtful", "Lost"}

BORROWER_TYPES = ("Individual", "Group", "Cooperative", "Corporate")


@dataclass
class Loan:
    borrower_id: str
    borrower_name: str
    borrower_type: str
    insider: bool
    insider_relationship: str
    facility_id: str
    outstanding: float
    days_past_due: int
    sector: str = ""
    restructured: bool = False
    row: int = 0


@dataclass
class Breach:
    code: str
    title: str
    detail: str
    value: float | None = None
    limit: float | None = None


@dataclass
class PrudentialResult:
    sfp: dict[str, float]
    pl: dict[str, float]
    totals: dict[str, float]
    ratios: list[dict]
    classification: list[dict]
    exposures: list[dict]
    insider_total: float
    breaches: list[Breach] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def classify(dpd: int) -> tuple[str, float]:
    for name, lo, hi, rate in LOAN_CLASSES:
        if dpd >= lo and (hi is None or dpd <= hi):
            return name, rate
    return "Performing", 0.01


def _sum(values: dict[str, float], lines: Iterable[tuple[str, str, str]], *groups: str) -> float:
    return sum(values.get(code, 0.0) for code, _, g in lines if g in groups)


def compute(
    sfp: dict[str, float],
    pl: dict[str, float],
    loans: list[Loan],
    licence_category: str,
    rwa_override: float | None = None,
    qualifying_capital_override: float | None = None,
) -> PrudentialResult:
    warnings: list[str] = []
    breaches: list[Breach] = []

    gross_loans = sfp.get("A07", 0.0)
    impairment = sfp.get("A08", 0.0)
    net_loans = gross_loans - impairment
    total_assets = (
        _sum(sfp, SFP_LINES, "liquid0", "liquid20", "asset", "ppe", "intangible") + net_loans
    )
    deposits = _sum(sfp, SFP_LINES, "deposit")
    total_liabilities = deposits + _sum(sfp, SFP_LINES, "liability")
    equity = _sum(sfp, SFP_LINES, "equity")

    interest_income = _sum(pl, PL_LINES, "interest_income")
    interest_expense = _sum(pl, PL_LINES, "interest_expense")
    nii = interest_income - interest_expense
    operating_income = nii + _sum(pl, PL_LINES, "other_income")
    pbt = operating_income - _sum(pl, PL_LINES, "impairment") - _sum(pl, PL_LINES, "opex")
    pat = pbt - pl.get("X07", 0.0)

    if abs(total_assets - (total_liabilities + equity)) > 1.0:
        warnings.append(
            f"Statement of financial position does not balance: total assets ₦{total_assets:,.2f} vs "
            f"liabilities + equity ₦{total_liabilities + equity:,.2f} "
            f"(difference ₦{total_assets - total_liabilities - equity:,.2f})."
        )

    shf = equity
    intangibles = sfp.get("A12", 0.0)
    qualifying = qualifying_capital_override if qualifying_capital_override is not None else shf - intangibles
    if rwa_override is not None:
        rwa = rwa_override
    else:
        rwa = (
            _sum(sfp, SFP_LINES, "liquid0") * RISK_WEIGHTS["liquid0"]
            + _sum(sfp, SFP_LINES, "liquid20") * RISK_WEIGHTS["liquid20"]
            + _sum(sfp, SFP_LINES, "asset") * RISK_WEIGHTS["asset"]
            + net_loans * RISK_WEIGHTS["loans_net"]
            + sfp.get("A11", 0.0) * RISK_WEIGHTS["ppe"]
        )
    liquid_assets = _sum(sfp, SFP_LINES, "liquid0", "liquid20")
    ppe = sfp.get("A11", 0.0)
    minimum_capital = MINIMUM_CAPITAL.get(licence_category, 0.0)

    def ratio(n: float, d: float) -> float | None:
        return n / d if d > 0 else None

    car = ratio(qualifying, rwa)
    liquidity = ratio(liquid_assets, deposits)
    fixed = ratio(ppe, shf) if shf > 0 else None

    ratios = [
        _ratio_row("CAR", "Capital adequacy ratio", car, LIMITS["car_min"], ">=", f"Qualifying capital ₦{qualifying:,.2f} / risk-weighted assets ₦{rwa:,.2f}"),
        _ratio_row("LIQ", "Liquidity ratio", liquidity, LIMITS["liquidity_min"], ">=", f"Liquid assets ₦{liquid_assets:,.2f} / deposit liabilities ₦{deposits:,.2f}"),
        _ratio_row("FIX", "Fixed assets to shareholders' funds", fixed, LIMITS["fixed_assets_max"], "<=", f"PPE ₦{ppe:,.2f} / shareholders' funds ₦{shf:,.2f}"),
        {
            "code": "MIN",
            "name": f"Shareholders' funds vs minimum capital ({LICENCE_CATEGORIES.get(licence_category, licence_category)})",
            "value": shf,
            "limit": minimum_capital,
            "operator": ">=",
            "kind": "money",
            "status": "Compliant" if shf >= minimum_capital else "Breach",
            "basis": f"Shareholders' funds unimpaired by losses ₦{shf:,.2f}; minimum ₦{minimum_capital:,.2f}",
        },
    ]
    for r in ratios:
        if r["status"] == "Breach":
            breaches.append(Breach(r["code"], r["name"], r["basis"], r["value"], r["limit"]))
        elif r["status"] == "Not computable":
            warnings.append(f"{r['name']} could not be computed — {r['basis']}.")
    if shf <= 0:
        breaches.append(Breach("SHF", "Shareholders' funds impaired", f"Shareholders' funds are ₦{shf:,.2f}; capital is fully impaired by losses.", shf, 0.0))

    # Loan classification and provisioning
    buckets = {name: {"class": name, "count": 0, "outstanding": 0.0, "rate": rate, "provision": 0.0} for name, _, _, rate in LOAN_CLASSES}
    for loan in loans:
        name, rate = classify(loan.days_past_due)
        b = buckets[name]
        b["count"] += 1
        b["outstanding"] += loan.outstanding
        b["provision"] += loan.outstanding * rate
    classification = list(buckets.values())
    book_total = sum(b["outstanding"] for b in classification)
    npl = sum(b["outstanding"] for b in classification if b["class"] in NON_PERFORMING)
    required_provision = sum(b["provision"] for b in classification)

    if loans and gross_loans > 0 and abs(book_total - gross_loans) > max(1.0, 0.005 * gross_loans):
        warnings.append(
            f"Loan book total ₦{book_total:,.2f} does not reconcile to gross loans in the statement of financial position "
            f"₦{gross_loans:,.2f} (difference ₦{book_total - gross_loans:,.2f})."
        )
    if not loans:
        warnings.append("No loan book was supplied — loan classification, provisioning and exposure tests are empty.")

    provision_gap = required_provision - impairment
    rrr = sfp.get("E04", 0.0)
    if provision_gap > 1.0 and rrr + 1.0 < provision_gap:
        warnings.append(
            f"Prudential provision ₦{required_provision:,.2f} exceeds the IFRS impairment allowance ₦{impairment:,.2f} by "
            f"₦{provision_gap:,.2f}; the regulatory risk reserve holds ₦{rrr:,.2f}."
        )

    # Exposures — aggregate facilities per borrower
    by_borrower: dict[str, dict] = {}
    insider_total = 0.0
    for loan in loans:
        key = loan.borrower_id or loan.borrower_name
        e = by_borrower.setdefault(key, {
            "borrower_id": loan.borrower_id,
            "borrower_name": loan.borrower_name,
            "borrower_type": loan.borrower_type,
            "insider": False,
            "insider_relationship": "",
            "facilities": 0,
            "outstanding": 0.0,
            "worst_class": "Performing",
        })
        e["facilities"] += 1
        e["outstanding"] += loan.outstanding
        if loan.insider:
            e["insider"] = True
            e["insider_relationship"] = e["insider_relationship"] or loan.insider_relationship
            insider_total += loan.outstanding
        cls, _ = classify(loan.days_past_due)
        if [c[0] for c in LOAN_CLASSES].index(cls) > [c[0] for c in LOAN_CLASSES].index(e["worst_class"]):
            e["worst_class"] = cls
    exposures = sorted(by_borrower.values(), key=lambda e: e["outstanding"], reverse=True)
    for e in exposures:
        limit_rate = LIMITS["single_obligor_individual"] if e["borrower_type"] == "Individual" else LIMITS["single_obligor_other"]
        e["limit_rate"] = limit_rate
        e["limit"] = limit_rate * shf if shf > 0 else 0.0
        e["pct_of_shf"] = e["outstanding"] / shf if shf > 0 else None
        e["breach"] = shf > 0 and e["outstanding"] > e["limit"] + 0.005
        if e["breach"]:
            breaches.append(Breach(
                "SOL",
                f"Single-obligor limit — {e['borrower_name']}",
                f"{e['borrower_type']} exposure ₦{e['outstanding']:,.2f} is {e['pct_of_shf']:.2%} of shareholders' funds (limit {limit_rate:.0%}).",
                e["outstanding"], e["limit"],
            ))
    insider_limit = LIMITS["insider_aggregate"] * shf if shf > 0 else 0.0
    if shf > 0 and insider_total > insider_limit + 0.005:
        breaches.append(Breach(
            "INS", "Aggregate insider-related credit",
            f"Insider-related credit ₦{insider_total:,.2f} is {insider_total / shf:.2%} of shareholders' funds (limit 5%).",
            insider_total, insider_limit,
        ))
    non_performing_insiders = [e for e in exposures if e["insider"] and e["worst_class"] in NON_PERFORMING]
    if non_performing_insiders:
        warnings.append(
            f"{len(non_performing_insiders)} insider-related exposure(s) are non-performing; a director whose facility stays non-performing "
            "for more than one year must cease to be on the board (Code of Corporate Governance s.5.2.19)."
        )

    totals = {
        "total_assets": total_assets,
        "net_loans": net_loans,
        "deposits": deposits,
        "total_liabilities": total_liabilities,
        "equity": equity,
        "shareholders_funds": shf,
        "qualifying_capital": qualifying,
        "risk_weighted_assets": rwa,
        "liquid_assets": liquid_assets,
        "interest_income": interest_income,
        "interest_expense": interest_expense,
        "net_interest_income": nii,
        "operating_income": operating_income,
        "profit_before_tax": pbt,
        "profit_after_tax": pat,
        "loan_book_total": book_total,
        "non_performing_loans": npl,
        "npl_ratio": npl / book_total if book_total > 0 else 0.0,
        "required_provision": required_provision,
        "impairment_allowance": impairment,
        "provision_gap": provision_gap,
        "insider_total": insider_total,
        "insider_limit": insider_limit,
        "minimum_capital": minimum_capital,
        "rwa_source_override": 1.0 if rwa_override is not None else 0.0,
        "qualifying_source_override": 1.0 if qualifying_capital_override is not None else 0.0,
    }
    return PrudentialResult(sfp, pl, totals, ratios, classification, exposures, insider_total, breaches, warnings)


def _ratio_row(code: str, name: str, value: float | None, limit: float, op: str, basis: str) -> dict:
    if value is None:
        status = "Not computable"
    elif op == ">=":
        status = "Compliant" if value >= limit else "Breach"
    else:
        status = "Compliant" if value <= limit else "Breach"
    return {"code": code, "name": name, "value": value, "limit": limit, "operator": op, "kind": "ratio", "status": status, "basis": basis}
