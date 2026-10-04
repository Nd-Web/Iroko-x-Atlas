"""
services/regulatory_returns/builders.py

Validate a return's inputs, compute its figures and render the documents.

    prepared = prepare(return_id, payload, upload_bytes)
    preview(prepared)   -> JSON summary: errors, warnings, breaches, key figures
    render(prepared)    -> [(filename, bytes, media_type), ...]

Generation is deterministic: every sentence comes from the inputs and the
rules in catalog/prudential — no model-written text — so the same inputs
always produce the same filing. Rendering refuses while errors remain, and
every breach must carry the bank's own remediation text before it can be
reported.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from docx.enum.text import WD_ALIGN_PARAGRAPH
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from . import templates
from .calendar import Period, due_date, fy_end_month_for, parse_period
from .catalog import LICENCE_CATEGORIES, PROFILE_FIELDS, RETURNS_BY_ID, Field, ReturnSpec
from .docx_kit import ReturnDocument, abbreviation, long_date, naira, pct
from .prudential import LOAN_CLASSES, PL_LINES, SFP_LINES, compute

LAGOS = timezone(timedelta(hours=1))  # WAT, no daylight saving
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

REF_CODES = {
    "cbn-monthly-prudential": "CBN/MPR",
    "cbn-fraud-forgeries": "CBN/FFR",
    "cbn-cg-compliance": "CBN/CGR",
    "cbn-whistleblowing": "CBN/WBR",
    "nfiu-str": "NFIU/STR",
    "nfiu-ctr": "NFIU/CTR",
    "ndic-deposit-certification": "NDIC/DEP",
    "cbn-afs-submission": "CBN/AFS",
    "ndpc-compliance-audit": "NDPC/CAR",
}


class ReturnInputError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors[:5]))
        self.errors = errors


@dataclass
class Prepared:
    spec: ReturnSpec
    profile: dict
    period: Period | None
    letter_date: date
    reference: str
    data: dict
    remediation: dict[str, str]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    breaches: list[dict] = field(default_factory=list)  # {code, title, detail}
    figures: list[tuple[str, str]] = field(default_factory=list)
    ctx: dict[str, Any] = field(default_factory=dict)

    @property
    def remediation_missing(self) -> list[dict]:
        seen, out = set(), []
        for b in self.breaches:
            if b["code"] not in seen and not (self.remediation.get(b["code"]) or "").strip():
                seen.add(b["code"])
                out.append({"code": b["code"], "title": b.get("group") or b["title"]})
        return out


# ─── Field validation ─────────────────────────────────────────────────────────


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("₦", "").strip())
    except ValueError:
        return None


def _validate(fields: tuple[Field, ...], raw: dict, where: str, errors: list[str]) -> dict:
    clean: dict[str, Any] = {}
    for f in fields:
        value = raw.get(f.key)
        label = f"{where}{f.label}"
        empty = value is None or value == "" or (isinstance(value, list) and not value)
        if f.type == "bool":
            clean[f.key] = bool(value) if not isinstance(value, str) else value.strip().lower() in {"true", "yes", "y", "1"}
            continue
        if empty:
            if f.required:
                errors.append(f"{label} is required.")
            clean[f.key] = [] if f.type in ("table", "multiselect") else None
            continue
        if f.type in ("money", "number"):
            n = _parse_number(value)
            if n is None:
                errors.append(f"{label} must be a number.")
            elif n < 0:
                errors.append(f"{label} cannot be negative.")
            clean[f.key] = n
        elif f.type == "date":
            d = _parse_date(value)
            if d is None:
                errors.append(f"{label} must be a date (YYYY-MM-DD).")
            clean[f.key] = d
        elif f.type == "select":
            if f.options and value not in f.options:
                errors.append(f"{label} must be one of: {', '.join(f.options)}.")
            clean[f.key] = value
        elif f.type == "multiselect":
            values = value if isinstance(value, list) else [value]
            bad = [v for v in values if f.options and v not in f.options]
            if bad:
                errors.append(f"{label}: unknown option(s) {', '.join(map(str, bad))}.")
            clean[f.key] = [v for v in values if v not in bad]
        elif f.type == "table":
            rows = value if isinstance(value, list) else []
            clean_rows = []
            for i, row in enumerate(rows, start=1):
                if not isinstance(row, dict) or all(v in (None, "", False) for v in row.values()):
                    continue
                clean_rows.append(_validate(f.columns, row, f"{f.label} row {i}: ", errors))
            if f.required and not clean_rows:
                errors.append(f"{label}: add at least one row.")
            clean[f.key] = clean_rows
        else:
            clean[f.key] = str(value).strip()
    return clean


# ─── Prepare ──────────────────────────────────────────────────────────────────


def prepare(return_id: str, payload: dict, upload: bytes | None = None) -> Prepared:
    spec = RETURNS_BY_ID.get(return_id)
    if spec is None or not spec.generator:
        raise KeyError(return_id)
    errors: list[str] = []
    profile = _validate(PROFILE_FIELDS, payload.get("profile") or {}, "Institution profile — ", errors)
    if profile.get("licence_category") and profile["licence_category"] not in LICENCE_CATEGORIES:
        errors.append("Institution profile — licence category is not recognised.")
    fy_end_month = int(payload.get("fy_end_month") or 12)
    period = None
    if spec.period_type != "event":
        try:
            period = parse_period(spec.period_type, str(payload.get("period") or ""), fy_end_month_for(spec, fy_end_month))
        except ValueError as exc:
            errors.append(str(exc))
    letter_date = _parse_date(payload.get("letter_date")) or datetime.now(LAGOS).date()
    data = _validate(spec.fields, payload.get("data") or {}, "", errors)
    abbr = abbreviation(profile.get("institution_name") or "")
    reference = (str(payload.get("reference") or "").strip()
                 or f"{abbr}/{REF_CODES[spec.id]}/{period.key if period else letter_date.strftime('%Y%m%d')}")
    remediation = {str(k): str(v) for k, v in (payload.get("remediation") or {}).items()}
    p = Prepared(spec, profile, period, letter_date, reference, data, remediation, errors)
    if period and not errors:
        due = due_date(spec, period)
        if period.end >= letter_date:
            p.warnings.append(f"The period ({period.label}) has not ended yet — the return should be dated after {long_date(period.end)}.")
        if due and letter_date > due:
            p.warnings.append(f"This return was due on {long_date(due)}; it is late as at the letter date. Late rendition attracts regulatory sanctions.")
        p.ctx["due"] = due
    if not errors:
        _COMPUTE[spec.id](p, upload)
    return p


def preview(p: Prepared) -> dict:
    return {
        "return_id": p.spec.id,
        "title": p.spec.title,
        "reference": p.reference,
        "period": p.period.label if p.period else None,
        "due": p.ctx["due"].isoformat() if p.ctx.get("due") else None,
        "errors": p.errors,
        "warnings": p.warnings,
        "breaches": p.breaches,
        "remediation_required": p.remediation_missing,
        "figures": [{"label": k, "value": v} for k, v in p.figures],
        "ready": not p.errors and not p.remediation_missing,
        "outputs": list(p.spec.outputs),
        "submission_notes": list(p.spec.submission_notes),
        "verification_notes": list(p.spec.verification_notes),
    }


def render(p: Prepared) -> list[tuple[str, bytes, str]]:
    if p.errors:
        raise ReturnInputError(p.errors)
    missing = p.remediation_missing
    if missing:
        raise ReturnInputError([f"Enter the bank's remediation plan for: {m['title']}." for m in missing])
    return _RENDER[p.spec.id](p)


# ─── Shared helpers ───────────────────────────────────────────────────────────


def _doc(p: Prepared, landscape: bool = False) -> ReturnDocument:
    return ReturnDocument(p.profile, p.reference, landscape=landscape)


def _filename(p: Prepared, ext: str) -> str:
    stem = p.reference.replace("/", "_").replace(" ", "")
    return f"{stem}.{ext}"


def _md(p: Prepared) -> tuple[str, str]:
    return (p.profile.get("md_ceo_name") or "", "Managing Director/Chief Executive Officer")


def _cco(p: Prepared) -> tuple[str, str]:
    return (p.profile.get("cco_name") or "", "Chief Compliance Officer")


def _cfo(p: Prepared) -> tuple[str, str]:
    return (p.profile.get("cfo_name") or "", "Head, Finance")


_PCT_HEADERS = {"% of SHF", "Limit", "Provision rate"}


def _xlsx(sheets: list[tuple[str, list[str], list[list[Any]]]]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    head_font, head_fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F3A5F")
    for name, headers, rows in sheets:
        ws = wb.create_sheet(name[:31])
        ws.append(headers)
        for cell in ws[1]:
            cell.font, cell.fill = head_font, head_fill
        for row in rows:
            ws.append([v.isoformat() if isinstance(v, date) else v for v in row])
        for col in ws.columns:
            letter = col[0].column_letter
            width = max(len(str(c.value or "")) for c in col)
            ws.column_dimensions[letter].width = min(max(width + 2, 10), 60)
            is_pct = col[0].value in _PCT_HEADERS
            for c in col[1:]:
                if isinstance(c.value, float):
                    c.number_format = "0.00%" if is_pct else "#,##0.00"
        ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _breach_section(d: ReturnDocument, p: Prepared, heading: str) -> None:
    d.heading(heading)
    if not p.breaches:
        d.para("No exception to report for the period.")
        return
    seen: set[str] = set()
    rows = [[b["title"], b["detail"]] for b in p.breaches]
    d.table(["Exception", "Particulars"], rows, widths_cm=(6, 10.5))
    d.heading("Remediation plan", 2)
    for b in p.breaches:
        if b["code"] in seen:
            continue
        seen.add(b["code"])
        d.para(f"{b.get('group') or b['title']}:", bold=True)
        d.para(p.remediation.get(b["code"], "").strip())


def _period_end_text(p: Prepared) -> str:
    return long_date(p.period.end) if p.period else ""


# ─── Monthly prudential returns ───────────────────────────────────────────────


def _compute_prudential(p: Prepared, upload: bytes | None) -> None:
    if not upload:
        p.errors.append("Upload the completed prudential input workbook (download the template first).")
        return
    try:
        parsed = templates.parse_prudential(upload)
    except templates.TemplateError as exc:
        p.errors.extend(exc.problems)
        return
    p.errors.extend(parsed.problems)
    if p.errors:
        return
    res = compute(
        parsed.sfp, parsed.pl, parsed.loans, p.profile["licence_category"],
        rwa_override=p.data.get("risk_weighted_assets_override"),
        qualifying_capital_override=p.data.get("qualifying_capital_override"),
    )
    p.warnings.extend(res.warnings)
    p.breaches = [
        {"code": b.code, "title": b.title, "detail": b.detail, **({"group": "Single-obligor limit breaches"} if b.code == "SOL" else {})}
        for b in res.breaches
    ]
    t = res.totals
    p.ctx["res"] = res
    p.figures = [
        ("Total assets", f"₦{naira(t['total_assets'])}"),
        ("Deposit liabilities", f"₦{naira(t['deposits'])}"),
        ("Shareholders' funds", f"₦{naira(t['shareholders_funds'])}"),
        ("Profit before tax (YTD)", f"₦{naira(t['profit_before_tax'])}"),
    ] + [(r["name"], pct(r["value"]) if r["kind"] == "ratio" else f"₦{naira(r['value'])}") for r in res.ratios] + [
        ("NPL ratio", pct(t["npl_ratio"])),
        ("Loans in book", str(sum(c["count"] for c in res.classification))),
    ]


def _render_prudential(p: Prepared) -> list[tuple[str, bytes, str]]:
    res = p.ctx["res"]
    t = res.totals
    inst = p.profile["institution_name"]
    d = _doc(p)
    d.letter_opening(p.letter_date, p.spec.recipient, f"Rendition of Monthly Returns for the Month Ended {_period_end_text(p)}")
    d.para(
        f"We hereby forward the monthly returns of {inst} for the month ended {_period_end_text(p)}, rendered through "
        "the CBN FinA application in compliance with Section 24 of the Banks and Other Financial Institutions Act 2020 "
        "and Section 5.3 of the Revised Regulatory and Supervisory Guidelines for Microfinance Banks in Nigeria."
    )
    d.para(
        f"As at the reporting date, the Bank's total assets stood at ₦{naira(t['total_assets'])}, deposit liabilities at "
        f"₦{naira(t['deposits'])}, net loans and advances at ₦{naira(t['net_loans'])} and shareholders' funds at "
        f"₦{naira(t['shareholders_funds'])}. Profit before tax for the financial year to date was ₦{naira(t['profit_before_tax'])}."
    )
    by_code = {r["code"]: r for r in res.ratios}
    ratio_text = (
        f"capital adequacy ratio {pct(by_code['CAR']['value'])} (minimum 10%), liquidity ratio {pct(by_code['LIQ']['value'])} "
        f"(minimum 20%) and fixed assets at {pct(by_code['FIX']['value'])} of shareholders' funds (maximum 20%); shareholders' funds "
        f"of ₦{naira(t['shareholders_funds'])} {'exceed' if t['shareholders_funds'] >= t['minimum_capital'] else 'fall short of'} the "
        f"₦{naira(t['minimum_capital'])} minimum capital for a {LICENCE_CATEGORIES[p.profile['licence_category']]}"
    )
    if p.breaches:
        d.para(
            f"The Bank's prudential position was: {ratio_text}. The exceptions to regulatory limits recorded in the month, "
            "together with management's remediation plans, are set out in Schedule 7."
        )
    else:
        d.para(f"The Bank's prudential position was: {ratio_text}. All prudential limits were complied with during the month.")
    d.para("The returns are certified by the Managing Director/Chief Executive Officer in line with Section 5.2.15 of the Code of Corporate Governance for Microfinance Banks in Nigeria. Kindly acknowledge receipt.")
    d.closing(
        [_md(p), _cco(p)],
        enclosures=[
            "Schedules 1–8: institution particulars; statement of financial position (MMFBR 300); profit or loss, year to date (MMFBR 1000); prudential ratios; loan classification and provisioning; single-obligor and insider exposures; exceptions and remediation; basis of preparation",
            "Certification by the Managing Director/Chief Executive Officer",
        ],
        cc=p.spec.cc,
    )

    d.page_break()
    d.heading("Schedule 1 — Institution particulars")
    d.key_values([
        ("Institution", inst),
        ("Licence category", LICENCE_CATEGORIES.get(p.profile["licence_category"], "")),
        ("CBN licence number", p.profile.get("cbn_licence_no") or ""),
        ("RC number", p.profile.get("rc_number") or ""),
        ("Head office", p.profile.get("head_office_address") or ""),
        ("Reporting period", f"Month ended {_period_end_text(p)}"),
        ("Managing Director/CEO", p.profile.get("md_ceo_name") or ""),
        ("Chief Compliance Officer", p.profile.get("cco_name") or ""),
        ("Contact", " · ".join(x for x in (p.profile.get("contact_email"), p.profile.get("contact_phone")) if x)),
    ])

    d.heading(f"Schedule 2 — Statement of financial position as at {_period_end_text(p)} (MMFBR 300)")
    sfp_rows: list[list[str]] = []
    sections = (("Assets", "A"), ("Liabilities", "L"), ("Equity", "E"))
    for title, prefix in sections:
        sfp_rows.append(["", title.upper(), ""])
        for code, label, _ in SFP_LINES:
            if code.startswith(prefix):
                v = res.sfp.get(code, 0.0)
                sfp_rows.append([code, label, naira(-v if code == "A08" else v, dash_zero=True)])
        if prefix == "A":
            sfp_rows.append(["", "Total assets", naira(t["total_assets"])])
        if prefix == "L":
            sfp_rows.append(["", "Total deposit liabilities", naira(t["deposits"])])
            sfp_rows.append(["", "Total liabilities", naira(t["total_liabilities"])])
        if prefix == "E":
            sfp_rows.append(["", "Total equity (shareholders' funds)", naira(t["equity"])])
            sfp_rows.append(["", "Total liabilities and equity", naira(t["total_liabilities"] + t["equity"])])
    d.table(["Code", "Line item", "₦"], sfp_rows, widths_cm=(1.6, 10.9, 4), numeric_cols=(2,),
            bold_rows=[i for i, r in enumerate(sfp_rows) if not r[0]])

    d.heading(f"Schedule 3 — Statement of profit or loss for the period ended {_period_end_text(p)} (MMFBR 1000, year to date)")
    pl = res.pl
    pl_rows = [[c, l, naira(pl.get(c, 0.0), dash_zero=True)] for c, l, _ in PL_LINES if c in ("I01", "I02")]
    pl_rows.append(["", "Total interest income", naira(t["interest_income"])])
    pl_rows += [[c, l, naira(pl.get(c, 0.0), dash_zero=True)] for c, l, _ in PL_LINES if c in ("X01", "X02")]
    pl_rows.append(["", "Net interest income", naira(t["net_interest_income"])])
    pl_rows += [[c, l, naira(pl.get(c, 0.0), dash_zero=True)] for c, l, _ in PL_LINES if c in ("I03", "I04")]
    pl_rows.append(["", "Operating income", naira(t["operating_income"])])
    pl_rows += [[c, l, naira(pl.get(c, 0.0), dash_zero=True)] for c, l, _ in PL_LINES if c in ("X03", "X04", "X05", "X06")]
    pl_rows.append(["", "Profit / (loss) before tax", naira(t["profit_before_tax"])])
    pl_rows.append(["X07", "Income tax expense", naira(pl.get("X07", 0.0), dash_zero=True)])
    pl_rows.append(["", "Profit / (loss) after tax", naira(t["profit_after_tax"])])
    d.table(["Code", "Line item", "₦"], pl_rows, widths_cm=(1.6, 10.9, 4), numeric_cols=(2,),
            bold_rows=[i for i, r in enumerate(pl_rows) if not r[0]])

    d.heading("Schedule 4 — Prudential ratios")
    d.table(
        ["Measure", "Actual", "Regulatory requirement", "Status"],
        [[
            r["name"],
            pct(r["value"]) if r["kind"] == "ratio" else f"₦{naira(r['value'])}",
            (("Minimum " if r["operator"] == ">=" else "Maximum ") + (pct(r["limit"], 0) if r["kind"] == "ratio" else f"₦{naira(r['limit'])}")),
            r["status"],
        ] for r in res.ratios],
        widths_cm=(6.5, 3.2, 4.3, 2.5), numeric_cols=(1,),
    )

    d.heading("Schedule 5 — Loan classification and provisioning")
    cls_rows = []
    for (name, lo, hi, rate), c in zip(LOAN_CLASSES, res.classification):
        band = f"{lo}–{hi}" if hi is not None else f"Above {lo - 1}"
        cls_rows.append([name, band, str(c["count"]), naira(c["outstanding"]), pct(rate, 0), naira(c["provision"])])
    cls_rows.append(["Total", "", str(sum(c["count"] for c in res.classification)), naira(t["loan_book_total"]), "", naira(t["required_provision"])])
    d.table(["Classification", "Days past due", "No.", "Outstanding (₦)", "Provision rate", "Required provision (₦)"], cls_rows,
            widths_cm=(3, 2.6, 1.4, 3.6, 2.2, 3.7), numeric_cols=(2, 3, 4, 5), bold_last=True)
    d.key_values([
        ("Non-performing loans (substandard, doubtful, lost)", f"₦{naira(t['non_performing_loans'])}"),
        ("NPL ratio", pct(t["npl_ratio"])),
        ("Prudential provision required", f"₦{naira(t['required_provision'])}"),
        ("IFRS impairment allowance held", f"₦{naira(t['impairment_allowance'])}"),
        ("Regulatory risk reserve", f"₦{naira(res.sfp.get('E04', 0.0))}"),
    ])

    d.heading("Schedule 6 — Single-obligor and insider-related exposures")
    shf = t["shareholders_funds"]
    top = [e for e in res.exposures if e["breach"]] + [e for e in res.exposures if not e["breach"]][: max(0, 20 - sum(1 for e in res.exposures if e["breach"]))]
    if top:
        d.para("Twenty largest exposures, with every exposure above the single-obligor limit:", italic=True)
        d.table(
            ["Borrower", "Type", "Facilities", "Outstanding (₦)", "% of SHF", "Limit", "Status"],
            [[e["borrower_name"], e["borrower_type"], str(e["facilities"]), naira(e["outstanding"]), pct(e["pct_of_shf"]), pct(e["limit_rate"], 0), "Breach" if e["breach"] else "Within limit"] for e in top],
            widths_cm=(4.5, 2.2, 1.6, 3, 1.8, 1.4, 2), numeric_cols=(2, 3, 4, 5),
        )
    else:
        d.para("No loan book was supplied for the month.")
    insiders = [e for e in res.exposures if e["insider"]]
    d.heading("Insider-related credit", 2)
    if insiders:
        d.table(
            ["Borrower", "Relationship", "Outstanding (₦)", "Classification"],
            [[e["borrower_name"], e["insider_relationship"] or "—", naira(e["outstanding"]), e["worst_class"]] for e in insiders]
            + [["Total insider-related credit", "", naira(t["insider_total"]), f"{pct(t['insider_total'] / shf) if shf > 0 else '—'} of SHF (limit 5%)"]],
            widths_cm=(5, 4, 3.5, 4), numeric_cols=(2,), bold_last=True,
        )
    else:
        d.para("The Bank had no insider-related credit outstanding at the reporting date.")

    _breach_section(d, p, "Schedule 7 — Exceptions and remediation")

    d.heading("Schedule 8 — Basis of preparation")
    rwa_note = (
        "Risk-weighted assets are the figure computed in the Bank's FinA return."
        if t["rwa_source_override"] else
        "Risk-weighted assets apply 0% to cash, balances with the CBN and FGN securities; 20% to balances with and placements in banks and OFIs; and 100% to net loans, other investments, other assets and property, plant and equipment."
    )
    qc_note = (
        "Qualifying capital is the figure computed in the Bank's FinA return."
        if t["qualifying_source_override"] else
        "Qualifying capital is total equity less intangible assets."
    )
    d.bullets([
        "Figures are drawn from the Bank's general ledger at the reporting date and agree with the FinA submission for the month.",
        "The statement of profit or loss is cumulative for the financial year to date.",
        qc_note,
        rwa_note,
        "Liquid assets comprise cash, balances with the CBN, balances with banks and OFIs, placements maturing within 90 days and FGN securities; the liquidity ratio is liquid assets over total deposit liabilities.",
        "Shareholders' funds unimpaired by losses are total equity, net of accumulated losses; single-obligor and insider limits are measured against this amount.",
        "Loans are classified by days past due — performing (0–30), pass and watch (31–59), substandard (60–90), doubtful (91–180) and lost (above 180) — with provisions of 1%, 5%, 20%, 50% and 100% respectively.",
    ])

    d.page_break()
    d.heading("Certification by the Managing Director/Chief Executive Officer")
    d.para(
        f"I, {p.profile['md_ceo_name']}, Managing Director/Chief Executive Officer of {inst}, certify that I have reviewed "
        f"the returns for the month ended {_period_end_text(p)} and that, based on my knowledge:"
    )
    d.numbered([
        "the returns do not contain any untrue statement of a material fact; and",
        "the financial statements and other financial information in the returns fairly represent, in all material respects, the financial condition and results of operations of the Bank as of, and for, the period presented.",
    ])
    d.para("Made pursuant to Section 5.2.15 of the Code of Corporate Governance for Microfinance Banks in Nigeria.", italic=True, size=9)
    d.signatures([_md(p)])
    d.para("Prepared by:", bold=True)
    d.signatures([s for s in (_cfo(p), _cco(p)) if s[0]])

    sheets = [
        ("MMFBR 300 SFP", ["Code", "Line item", "Amount (NGN)"], [[c, l, float(res.sfp.get(c, 0.0))] for c, l, _ in SFP_LINES]),
        ("MMFBR 1000 PL (YTD)", ["Code", "Line item", "Amount (NGN)"], [[c, l, float(res.pl.get(c, 0.0))] for c, l, _ in PL_LINES]),
        ("Prudential ratios", ["Measure", "Actual", "Requirement", "Status", "Basis"],
         [[r["name"],
           pct(r["value"]) if r["kind"] == "ratio" else naira(r["value"]),
           ("Min " if r["operator"] == ">=" else "Max ") + (pct(r["limit"], 0) if r["kind"] == "ratio" else naira(r["limit"])),
           r["status"], r["basis"]] for r in res.ratios]),
        ("Loan classification", ["Classification", "Count", "Outstanding (NGN)", "Provision rate", "Required provision (NGN)"],
         [[c["class"], c["count"], float(c["outstanding"]), c["rate"], float(c["provision"])] for c in res.classification]),
        ("Exposures", ["Borrower ID", "Borrower", "Type", "Insider", "Relationship", "Facilities", "Outstanding (NGN)", "% of SHF", "Limit", "Worst class", "Status"],
         [[e["borrower_id"], e["borrower_name"], e["borrower_type"], "Y" if e["insider"] else "N", e["insider_relationship"], e["facilities"], float(e["outstanding"]), e["pct_of_shf"], e["limit_rate"], e["worst_class"], "Breach" if e["breach"] else "Within limit"] for e in res.exposures]),
        ("Exceptions", ["Code", "Exception", "Particulars", "Remediation"],
         [[b["code"], b["title"], b["detail"], p.remediation.get(b["code"], "")] for b in p.breaches]),
    ]
    return [
        (_filename(p, "docx"), d.to_bytes(), DOCX),
        (_filename(p, "xlsx"), _xlsx(sheets), XLSX),
    ]


# ─── Frauds and forgeries ─────────────────────────────────────────────────────


def _compute_fraud(p: Prepared, upload: bytes | None) -> None:
    cases = p.data["incidents"]
    nil = p.data["nil_return"]
    if nil and cases:
        p.errors.append("Untick 'nil return' or remove the cases — a nil return cannot list cases.")
    if not nil and not cases:
        p.errors.append("Add the month's fraud and forgery cases, or tick 'nil return' if there were none.")
    for c in cases:
        if c["date_discovered"] and p.period and not (p.period.start <= c["date_discovered"] <= p.period.end):
            p.warnings.append(f"Case {c['case_ref']}: discovered {c['date_discovered'].isoformat()}, outside {p.period.label}. Report it in the month it was discovered unless it is an update.")
        if c["actual_loss"] is not None and c["amount_involved"] is not None and c["actual_loss"] > c["amount_involved"]:
            p.errors.append(f"Case {c['case_ref']}: actual loss exceeds the amount involved.")
        if (c.get("amount_recovered") or 0) > (c["actual_loss"] or 0) + 0.005 and (c["actual_loss"] or 0) > 0:
            p.warnings.append(f"Case {c['case_ref']}: amount recovered exceeds the actual loss.")
    p.ctx["totals"] = {
        "involved": sum(c["amount_involved"] or 0 for c in cases),
        "loss": sum(c["actual_loss"] or 0 for c in cases),
        "recovered": sum(c.get("amount_recovered") or 0 for c in cases),
        "staff": sum(1 for c in cases if (c.get("staff_involved") or "").strip().lower() not in ("", "none", "nil", "n/a")),
    }
    tt = p.ctx["totals"]
    p.figures = [("Cases", str(len(cases)) if cases else "Nil return"), ("Amount involved", f"₦{naira(tt['involved'])}"),
                 ("Actual loss", f"₦{naira(tt['loss'])}"), ("Recovered", f"₦{naira(tt['recovered'])}"), ("Cases involving staff", str(tt["staff"]))]


def _render_fraud(p: Prepared) -> list[tuple[str, bytes, str]]:
    cases, tt = p.data["incidents"], p.ctx["totals"]
    inst = p.profile["institution_name"]
    d = _doc(p)
    d.letter_opening(p.letter_date, p.spec.recipient, f"Monthly Return on Frauds and Forgeries for the Month Ended {_period_end_text(p)}")
    if not cases:
        d.para(f"We hereby render a NIL return on frauds and forgeries for {inst} for the month ended {_period_end_text(p)}. No case of fraud or forgery, attempted or successful, was recorded or discovered in the Bank during the month.")
        d.para("Kindly acknowledge receipt.")
        d.closing([_md(p), _cco(p)], cc=p.spec.cc)
        return [(_filename(p, "docx"), d.to_bytes(), DOCX)]
    d.para(
        f"We hereby render the return on frauds and forgeries of {inst} for the month ended {_period_end_text(p)}. "
        f"{len(cases)} case(s) were recorded in the month, involving a total of ₦{naira(tt['involved'])}, with actual loss to the Bank of "
        f"₦{naira(tt['loss'])} and recoveries of ₦{naira(tt['recovered'])}. {tt['staff']} case(s) involved members of staff."
    )
    d.para("The particulars of each case and the action taken are set out in the attached schedule. Kindly acknowledge receipt.")
    d.closing([_md(p), _cco(p)], enclosures=["Schedule of frauds and forgeries"], cc=p.spec.cc)
    d.page_break()
    d.heading(f"Schedule of frauds and forgeries — month ended {_period_end_text(p)}")
    d.table(
        ["Ref", "Discovered", "Branch", "Category", "Involved (₦)", "Loss (₦)", "Recovered (₦)", "Status"],
        [[c["case_ref"], c["date_discovered"].isoformat() if c["date_discovered"] else "", c["branch"], c["category"], naira(c["amount_involved"]), naira(c["actual_loss"]), naira(c.get("amount_recovered") or 0), c["status"]] for c in cases]
        + [["Total", "", "", "", naira(tt["involved"]), naira(tt["loss"]), naira(tt["recovered"]), ""]],
        numeric_cols=(4, 5, 6), bold_last=True, font_size=8,
    )
    for c in cases:
        d.heading(f"Case {c['case_ref']} — {c['category']}", 2)
        d.key_values([
            ("Date occurred / discovered", f"{c['date_occurred'].isoformat() if c['date_occurred'] else '—'} / {c['date_discovered'].isoformat() if c['date_discovered'] else '—'}"),
            ("Branch / location", c["branch"]),
            ("Description", c["description"]),
            ("Staff involved", c.get("staff_involved") or "None"),
            ("Reported to the police", "Yes" if c.get("reported_to_police") else "No"),
            ("Status", c["status"]),
            ("Action taken", c["action_taken"]),
        ])
    sheet = ("Frauds and forgeries", ["Case ref", "Date occurred", "Date discovered", "Branch", "Category", "Description", "Amount involved (NGN)", "Actual loss (NGN)", "Recovered (NGN)", "Staff involved", "Police", "Status", "Action taken"],
             [[c["case_ref"], c["date_occurred"], c["date_discovered"], c["branch"], c["category"], c["description"], float(c["amount_involved"] or 0), float(c["actual_loss"] or 0), float(c.get("amount_recovered") or 0), c.get("staff_involved") or "", "Y" if c.get("reported_to_police") else "N", c["status"], c["action_taken"]] for c in cases])
    return [(_filename(p, "docx"), d.to_bytes(), DOCX), (_filename(p, "xlsx"), _xlsx([sheet]), XLSX)]


# ─── Corporate governance ─────────────────────────────────────────────────────

_EXEC_ROLES = {"MD/CEO", "Executive Director"}
_NED_ROLES = {"Chairman", "Non-Executive Director", "Independent Non-Executive Director"}
_BOARD_SIZE = {"unit_tier1": (5, 7), "unit_tier2": (5, 7), "state": (5, 9), "national": (7, 12)}


def _years(start: date | None, end: date) -> float:
    return (end - start).days / 365.25 if start else 0.0


def _compute_cg(p: Prepared, upload: bytes | None) -> None:
    board, committees = p.data["board"], p.data["committees"]
    cat = p.profile["licence_category"]
    end = p.period.end
    unit = cat.startswith("unit")
    checks: list[dict] = []

    def check(code: str, section: str, requirement: str, ok: bool | None, comment: str) -> None:
        status = "Compliant" if ok else ("Not compliant" if ok is False else "For information")
        checks.append({"code": code, "section": section, "requirement": requirement, "status": status, "comment": comment})
        if ok is False:
            p.breaches.append({"code": code, "title": f"{requirement} (s.{section})", "detail": comment})

    size_lo, size_hi = _BOARD_SIZE[cat]
    n = len(board)
    check("CG-2.2.1", "2.2.1", "Board size", size_lo <= n <= size_hi, f"{n} directors; the Code requires {size_lo}–{size_hi} for a {LICENCE_CATEGORIES[cat]}.")
    eds = [b for b in board if b["role"] in _EXEC_ROLES]
    neds = [b for b in board if b["role"] in _NED_ROLES]
    check("CG-2.2.4", "2.2.4", "Non-executive directors outnumber executive directors", len(neds) > len(eds), f"{len(neds)} non-executive and {len(eds)} executive directors.")
    ined_needed = 2 if (cat == "national" or (cat == "state" and n > 7)) else 1
    ineds = [b for b in board if b["role"] == "Independent Non-Executive Director"]
    check("CG-2.2.5", "2.2.5", "Independent non-executive directors", len(ineds) >= ined_needed, f"{len(ineds)} INED(s); minimum {ined_needed}.")
    if unit:
        check("CG-2.2.2", "2.2.2", "MD/CEO is the only executive director (Unit MFB)", len(eds) <= 1, f"{len(eds)} executive director(s) on the board.")
    chairs = [b for b in board if b["role"] == "Chairman"]
    mds = [b for b in board if b["role"] == "MD/CEO"]
    separate = len(chairs) == 1 and len(mds) == 1 and chairs[0]["name"].strip().lower() != mds[0]["name"].strip().lower()
    check("CG-2.3.1", "2.3.1", "Separate Chairman and MD/CEO", separate, f"Chairman: {', '.join(c['name'] for c in chairs) or 'none recorded'}; MD/CEO: {', '.join(m['name'] for m in mds) or 'none recorded'}.")
    check("CG-2.3.2", "2.3.2", "Not more than two members of a family on the board", not p.data["family_members_on_board"],
          "More than two members of one family serve on the board." if p.data["family_members_on_board"] else "No more than two members of any family serve on the board.")
    unapproved = [b["name"] for b in board if not b.get("cbn_approved")]
    check("CG-2.4.1", "2.4.1", "Directors approved by the CBN", not unapproved, f"Awaiting CBN approval: {', '.join(unapproved)}." if unapproved else "All directors are CBN-approved.")
    over = []
    for b in board:
        yrs = _years(b["first_appointed"], end)
        if b["role"] == "Independent Non-Executive Director" and yrs > 8:
            over.append(f"{b['name']} (INED, {yrs:.1f} years; maximum 8)")
        elif b["role"] in ("Chairman", "Non-Executive Director") and yrs > 12:
            over.append(f"{b['name']} (NED, {yrs:.1f} years; maximum 12)")
        elif b["role"] == "MD/CEO" and yrs > 10:
            over.append(f"{b['name']} (MD/CEO, {yrs:.1f} years; maximum 10)")
    check("CG-2.4", "2.4.6–2.4.8", "Tenure limits", not over, "; ".join(over) if over else "All directors are within their tenure limits.")

    names = [c["name"] for c in committees]
    has = lambda key: any(key in nm for nm in names)  # noqa: E731
    combined = has("Risk & Audit")
    missing = []
    if not (has("Risk Management") or combined):
        missing.append("Risk Management")
    if not (has("Board Audit") or combined):
        missing.append("Audit")
    if combined and not unit and cat != "state":
        missing.append("separate Risk and Audit committees (combination allowed only for Unit and State MFBs)")
    for req in ("Governance & Nominations", "Credit"):
        if not has(req):
            missing.append(req)
    check("CG-2.5.1", "2.5.1", "Required board committees", not missing, f"Missing: {', '.join(missing)}." if missing else f"In place: {', '.join(names)}.")
    bad_chairs = [c["name"] for c in committees if c["chair_role"] not in ("Non-Executive Director", "Independent Non-Executive Director")]
    check("CG-2.5.6", "2.5.6", "Committees headed by non-executive directors", not bad_chairs, f"Not chaired by a NED: {', '.join(bad_chairs)}." if bad_chairs else "Every committee is chaired by a NED.")
    chair_on_committees = [c for c in chairs if (c.get("committees") or "").strip()]
    check("CG-2.5.5", "2.5.5", "Board Chairman not a member of any committee", not chair_on_committees,
          f"The Chairman sits on: {chair_on_committees[0]['committees']}." if chair_on_committees else "The Chairman sits on no board committee.")
    audit = [c for c in committees if "Audit" in c["name"]]
    if audit:
        a = audit[0]
        ok = (a["members"] or 0) >= 3 and (unit or a["chair_role"] == "Independent Non-Executive Director")
        check("CG-5.2.2", "5.2.2", "Audit committee: at least three NEDs, chaired by an INED (a NED may chair in a Unit MFB)", ok,
              f"{int(a['members'] or 0)} member(s); chaired by a {a['chair_role']}.")
    execs_on_audit = [b["name"] for b in board if b["role"] in _EXEC_ROLES and "audit" in (b.get("committees") or "").lower()]
    check("CG-2.5.8", "2.5.8", "MD/CEO and executive directors not on the audit committee", not execs_on_audit,
          f"On the audit committee: {', '.join(execs_on_audit)}." if execs_on_audit else "No executive director sits on the audit committee.")
    unapproved_charters = [c["name"] for c in committees if not c.get("charter_cbn_approved")]
    check("CG-2.5.4", "2.5.4", "Board and committee charters approved by the CBN", not unapproved_charters,
          f"Charter not yet approved: {', '.join(unapproved_charters)}." if unapproved_charters else "All charters are CBN-approved.")
    low_meetings = []
    if (p.data["board_meetings_in_period"] or 0) < 2:
        low_meetings.append(f"Board ({int(p.data['board_meetings_in_period'] or 0)})")
    low_meetings += [f"{c['name']} ({int(c['meetings_held'] or 0)})" for c in committees if (c["meetings_held"] or 0) < 2]
    check("CG-2.6.1", "2.6.1", "Board and committees meet at least once every quarter", not low_meetings,
          f"Fewer than two meetings in the half-year: {', '.join(low_meetings)}." if low_meetings else "The board and every committee met at least once in each quarter.")
    low_attendance = [
        f"{b['name']} ({int(b['board_meetings_attended'] or 0)}/{int(b['board_meetings_held'] or 0)})"
        for b in board if (b["board_meetings_held"] or 0) > 0 and (b["board_meetings_attended"] or 0) < (2 / 3) * b["board_meetings_held"]
    ]
    check("CG-2.6.3", "2.6.3", "Attendance of at least two-thirds of meetings (condition for re-election)", None if low_attendance else True,
          f"Below two-thirds: {', '.join(low_attendance)} — not eligible for re-election on current attendance." if low_attendance else "Every director attended at least two-thirds of meetings.")
    check("CG-5.2.10", "5.2.10", "External auditor appointment approved by the CBN", p.data["external_auditor_cbn_approved"], f"External auditor: {p.data['external_auditor']}.")
    check("CG-2.5.1R", "2.5.1", "Risk Officer and Internal Auditor reporting to the board committees",
          p.data["risk_officer_in_place"] and p.data["internal_auditor_in_place"],
          "Risk Officer and Internal Auditor in place." if p.data["risk_officer_in_place"] and p.data["internal_auditor_in_place"] else "Risk Officer and/or Internal Auditor not in place.")
    check("CG-5.2.7", "5.2.7", "Chief Compliance Officer in place", bool(p.profile.get("cco_name")), f"Chief Compliance Officer: {p.profile.get('cco_name') or 'not appointed'}.")
    appraisal = p.data.get("board_appraisal_date")
    appraisal_due = date(end.year, 3, 31)
    check("CG-2.8.2", "2.8.2", "Annual board appraisal forwarded to the CBN by 31 March", bool(appraisal and appraisal <= appraisal_due and appraisal.year == end.year),
          f"Forwarded on {appraisal.isoformat()}." if appraisal else f"No record of the {end.year - 1} appraisal being forwarded.")
    p.ctx["checks"] = checks
    passed = sum(1 for c in checks if c["status"] == "Compliant")
    p.figures = [("Directors", str(n)), ("Requirements tested", str(len(checks))), ("Compliant", str(passed)),
                 ("Not compliant", str(sum(1 for c in checks if c["status"] == "Not compliant")))]


def _render_cg(p: Prepared) -> list[tuple[str, bytes, str]]:
    checks, board, committees = p.ctx["checks"], p.data["board"], p.data["committees"]
    inst = p.profile["institution_name"]
    d = _doc(p)
    d.letter_opening(p.letter_date, p.spec.recipient, f"Returns on Compliance with the Code of Corporate Governance for the Half-year Ended {_period_end_text(p)}")
    failed = [c for c in checks if c["status"] == "Not compliant"]
    d.para(f"In compliance with Section 8.2 of the Code of Corporate Governance for Microfinance Banks in Nigeria, we hereby render the returns of {inst} on the status of its compliance with the Code for the half-year ended {_period_end_text(p)}.")
    if failed:
        d.para(f"The Bank complied with {len(checks) - len(failed)} of the {len(checks)} requirements reviewed. The {len(failed)} area(s) of non-compliance, with the Board's remediation plans, are disclosed in Schedule D.")
    else:
        d.para(f"The Bank complied with all {len(checks)} requirements reviewed during the period, as detailed in the attached compliance matrix.")
    if p.data.get("other_disclosures"):
        d.para(p.data["other_disclosures"])
    d.para("Kindly acknowledge receipt.")
    d.closing([_md(p), _cco(p)], enclosures=["Schedule A — Board composition", "Schedule B — Board committees", "Schedule C — Compliance matrix", "Schedule D — Non-compliance and remediation"])
    d.page_break()
    d.heading("Schedule A — Board composition")
    d.table(["Director", "Role", "First appointed", "Years in office", "CBN approved", "Attendance", "Committees"],
            [[b["name"], b["role"], b["first_appointed"].isoformat() if b["first_appointed"] else "", f"{_years(b['first_appointed'], p.period.end):.1f}", "Yes" if b.get("cbn_approved") else "No",
              f"{int(b['board_meetings_attended'] or 0)}/{int(b['board_meetings_held'] or 0)}", b.get("committees") or "—"] for b in board],
            numeric_cols=(3,), font_size=8)
    d.para(f"Board meetings held in the half-year: {int(p.data['board_meetings_in_period'] or 0)}.")
    d.heading("Schedule B — Board committees")
    d.table(["Committee", "Chaired by", "Chair's role", "Members", "Meetings in period", "Charter approved"],
            [[c["name"], c["chair"], c["chair_role"], str(int(c["members"] or 0)), str(int(c["meetings_held"] or 0)), "Yes" if c.get("charter_cbn_approved") else "No"] for c in committees],
            numeric_cols=(3, 4), font_size=8.5)
    d.heading("Schedule C — Compliance matrix")
    d.table(["Section", "Requirement", "Status", "Comment"], [[c["section"], c["requirement"], c["status"], c["comment"]] for c in checks],
            widths_cm=(1.8, 5.4, 2.4, 7), font_size=8.5)
    _breach_section(d, p, "Schedule D — Non-compliance and remediation")
    sheets = [
        ("Board", ["Director", "Role", "First appointed", "CBN approved", "Meetings held", "Meetings attended", "Committees"],
         [[b["name"], b["role"], b["first_appointed"], "Y" if b.get("cbn_approved") else "N", b["board_meetings_held"], b["board_meetings_attended"], b.get("committees") or ""] for b in board]),
        ("Committees", ["Committee", "Chair", "Chair role", "Members", "Meetings", "Charter approved"],
         [[c["name"], c["chair"], c["chair_role"], c["members"], c["meetings_held"], "Y" if c.get("charter_cbn_approved") else "N"] for c in committees]),
        ("Compliance matrix", ["Section", "Requirement", "Status", "Comment", "Remediation"],
         [[c["section"], c["requirement"], c["status"], c["comment"], p.remediation.get(c["code"], "") if c["status"] == "Not compliant" else ""] for c in checks]),
    ]
    return [(_filename(p, "docx"), d.to_bytes(), DOCX), (_filename(p, "xlsx"), _xlsx(sheets), XLSX)]


# ─── Whistle-blowing ──────────────────────────────────────────────────────────


def _compute_wb(p: Prepared, upload: bytes | None) -> None:
    x = p.data
    received, investigated, substantiated = int(x["cases_received"] or 0), int(x["cases_investigated"] or 0), int(x["cases_substantiated"] or 0)
    closed, pending = int(x["cases_closed"] or 0), int(x["cases_pending"] or 0)
    if substantiated > investigated:
        p.errors.append("Cases substantiated cannot exceed cases investigated.")
    if closed + pending != received:
        p.warnings.append(f"Closed ({closed}) plus pending ({pending}) does not equal cases received ({received}). If cases were brought forward from the previous half-year, say so in the case summary.")
    if received and not (x.get("case_summary") or "").strip():
        p.errors.append("Describe the nature of the cases and the actions taken.")
    if (x.get("retaliation_complaints") or 0) > 0:
        p.warnings.append("Retaliation complaints were reported; the return should state how each was handled.")
    if not x["policy_on_website"]:
        p.warnings.append("The whistle-blowing policy is not on the bank's website; CBN expects it to be published.")
    p.figures = [("Received", str(received)), ("Investigated", str(investigated)), ("Substantiated", str(substantiated)), ("Closed", str(closed)), ("Pending", str(pending))]


def _render_wb(p: Prepared) -> list[tuple[str, bytes, str]]:
    x, inst = p.data, p.profile["institution_name"]
    d = _doc(p)
    d.letter_opening(p.letter_date, p.spec.recipient, f"Returns on Compliance with the Whistle-blowing Policy for the Half-year Ended {_period_end_text(p)}")
    received = int(x["cases_received"] or 0)
    d.para(f"In compliance with Section 5.3.3 of the Code of Corporate Governance for Microfinance Banks in Nigeria, we hereby render the returns of {inst} on compliance with its whistle-blowing policy for the half-year ended {_period_end_text(p)}.")
    d.para(
        f"The Bank's whistle-blowing policy was approved by the Board on {long_date(x['policy_approval_date'])}"
        + (" and is published on the Bank's website." if x["policy_on_website"] else ".")
        + f" Concerns may be raised through: {x['channels'].strip().rstrip('.')}."
    )
    if received:
        d.para(f"{received} whistle-blowing report(s) were received in the period. Their status at the end of the period is set out below.")
    else:
        d.para("No whistle-blowing report was received during the period (nil return).")
    d.key_values([
        ("Reports received", str(received)),
        ("Reports investigated", str(int(x["cases_investigated"] or 0))),
        ("Reports substantiated", str(int(x["cases_substantiated"] or 0))),
        ("Reports closed", str(int(x["cases_closed"] or 0))),
        ("Reports pending at period end", str(int(x["cases_pending"] or 0))),
        ("Complaints of retaliation", str(int(x.get("retaliation_complaints") or 0))),
    ])
    if (x.get("case_summary") or "").strip():
        d.heading("Nature of reports and actions taken", 2)
        d.para(x["case_summary"])
    if (x.get("staff_awareness") or "").strip():
        d.heading("Staff awareness", 2)
        d.para(x["staff_awareness"])
    d.para("The identity of every whistle-blower has been kept confidential, and no whistle-blower suffered detriment for raising a concern in good faith. Kindly acknowledge receipt.")
    d.closing([_md(p), _cco(p)])
    return [(_filename(p, "docx"), d.to_bytes(), DOCX)]


# ─── Suspicious transaction report ────────────────────────────────────────────


def _parse_dt(text: str) -> datetime | None:
    text = (text or "").strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=LAGOS)
        except ValueError:
            continue
    return None


def _compute_str(p: Prepared, upload: bytes | None) -> None:
    detected = _parse_dt(p.data["detection_datetime"])
    if detected is None:
        p.errors.append("When the transaction was identified must be a date and time, e.g. 2026-10-02 14:30.")
        return
    txns = p.data["transactions"]
    total = sum(t["amount"] or 0 for t in txns)
    latest = max((t["date"] for t in txns if t["date"]), default=None)
    now = datetime.now(LAGOS)
    if latest:
        deadline = datetime.combine(latest, datetime.min.time(), LAGOS) + timedelta(days=1, hours=23, minutes=59)
        p.ctx["deadline"] = deadline
        if now > deadline:
            p.warnings.append(f"More than 24 hours have passed since the latest transaction ({latest.isoformat()}). File on goAML immediately and record the reason for the delay on the STR file.")
    if len((p.data["reasons"] or "").split()) < 25:
        p.warnings.append("The reasons for suspicion are brief. NFIU expects the facts observed, how they depart from the customer's profile and the checks made.")
    p.ctx.update(detected=detected, total=total)
    p.figures = [("Transactions", str(len(txns))), ("Total value", f"₦{naira(total)}"), ("Grounds cited", str(len(p.data["grounds"])))]


def _render_str(p: Prepared) -> list[tuple[str, bytes, str]]:
    x, inst = p.data, p.profile["institution_name"]
    d = _doc(p)
    d.para("STRICTLY CONFIDENTIAL — NOT TO BE DISCLOSED TO THE SUBJECT OR ANY THIRD PARTY", bold=True, size=9, align=WD_ALIGN_PARAGRAPH.CENTER)
    d.para("Disclosure that this report has been or will be made is an offence under Section 19(1)(a) of the Money Laundering (Prevention and Prohibition) Act 2022.", italic=True, size=8.5, align=WD_ALIGN_PARAGRAPH.CENTER)
    d.para("SUSPICIOUS TRANSACTION REPORT", bold=True, size=14, align=WD_ALIGN_PARAGRAPH.CENTER)
    d.para("Rendered to the Nigerian Financial Intelligence Unit under Section 7 of the Money Laundering (Prevention and Prohibition) Act 2022", size=9, align=WD_ALIGN_PARAGRAPH.CENTER)
    d.key_values([("Report reference", p.reference), ("Date of report", long_date(p.letter_date)), ("goAML submission reference", "")])
    d.heading("Part A — Reporting institution")
    d.key_values([
        ("Institution", inst), ("CBN licence number", p.profile.get("cbn_licence_no") or ""),
        ("Head office", p.profile.get("head_office_address") or ""),
        ("Chief Compliance Officer", p.profile.get("cco_name") or ""),
        ("Contact", " · ".join(v for v in (p.profile.get("contact_email"), p.profile.get("contact_phone")) if v)),
    ])
    d.heading("Part B — Subject of the report")
    d.key_values([
        ("Name", x["subject_name"]), ("Type", x["subject_type"]), ("Account number", x["account_number"]),
        ("BVN / RC number", x.get("bvn_or_rc") or ""), ("Address", x.get("subject_address") or ""),
        ("Occupation / business", x.get("occupation_or_business") or ""),
        ("Customer since", x["relationship_start"].isoformat() if x.get("relationship_start") else ""),
    ])
    d.heading("Part C — Transactions")
    txns = sorted(x["transactions"], key=lambda t: t["date"] or date.min)
    d.table(["Date", "Type", "Amount (₦)", "Counterparty", "Channel", "Narration"],
            [[t["date"].isoformat() if t["date"] else "", t["type"], naira(t["amount"]), t.get("counterparty") or "", t.get("channel") or "", t.get("narration") or ""] for t in txns]
            + [["Total", "", naira(p.ctx["total"]), "", "", ""]],
            numeric_cols=(2,), bold_last=True, font_size=8.5)
    d.heading("Part D — Grounds for suspicion (Section 7(1))")
    d.bullets(x["grounds"])
    d.heading("Part E — Reasons for suspicion")
    d.para(x["reasons"])
    d.para(f"The transaction(s) were identified as suspicious on {p.ctx['detected'].strftime('%d %B %Y at %H:%M')} (WAT).")
    d.heading("Part F — Action taken")
    d.para(x["action_taken"])
    d.heading("Part G — Declaration")
    d.para("I confirm that the information in this report is true to the best of my knowledge, has been drawn from the institution's records, and that the subject has not been informed of this report.")
    d.signatures([(x["reporting_officer"], "Reporting Officer"), _cco(p)])
    return [(_filename(p, "docx"), d.to_bytes(), DOCX)]


# ─── Currency transaction report ──────────────────────────────────────────────


def _compute_ctr(p: Prepared, upload: bytes | None) -> None:
    if not upload:
        p.errors.append("Upload the transactions workbook (download the template first).")
        return
    start, end = p.data["period_from"], p.data["period_to"]
    if start and end and start > end:
        p.errors.append("'Transactions from' must be on or before 'Transactions to'.")
        return
    try:
        txns, problems = templates.parse_transactions(upload)
    except templates.TemplateError as exc:
        p.errors.extend(exc.problems)
        return
    p.errors.extend(problems)
    if p.errors:
        return
    today = datetime.now(LAGOS).date()
    in_range = [t for t in txns if start <= t.date <= end]
    outside = len(txns) - len(in_range)
    if outside:
        p.warnings.append(f"{outside} transaction(s) fall outside {start.isoformat()} – {end.isoformat()} and were ignored.")
    qualifying = [t for t in in_range if t.amount > templates.CTR_THRESHOLDS[t.customer_type]]
    rows = []
    for t in sorted(qualifying, key=lambda t: t.date):
        deadline = t.date + timedelta(days=7)
        rows.append({"t": t, "deadline": deadline, "late": today > deadline})
    late = sum(1 for r in rows if r["late"])
    if late:
        p.warnings.append(f"{late} qualifying transaction(s) are past the 7-day filing window. File them immediately; late filing attracts ₦250,000–₦1,000,000 per day (s.11(3)).")
    p.ctx.update(rows=rows, scanned=len(in_range))
    p.figures = [("Transactions scanned", str(len(in_range))), ("Reportable", str(len(rows))),
                 ("Reportable value", f"₦{naira(sum(r['t'].amount for r in rows))}"), ("Past 7-day window", str(late))]


def _render_ctr(p: Prepared) -> list[tuple[str, bytes, str]]:
    rows, inst = p.ctx["rows"], p.profile["institution_name"]
    start, end = p.data["period_from"], p.data["period_to"]
    total = sum(r["t"].amount for r in rows)
    d = _doc(p, landscape=True)
    d.para("CONFIDENTIAL", bold=True, size=9, align=WD_ALIGN_PARAGRAPH.CENTER)
    d.para("CURRENCY TRANSACTION REPORT", bold=True, size=14, align=WD_ALIGN_PARAGRAPH.CENTER)
    d.para("Mandatory disclosure under Section 11(1) of the Money Laundering (Prevention and Prohibition) Act 2022", size=9, align=WD_ALIGN_PARAGRAPH.CENTER)
    d.key_values([
        ("Reporting institution", inst), ("Report reference", p.reference), ("Date of report", long_date(p.letter_date)),
        ("Transactions covered", f"{long_date(start)} to {long_date(end)}"),
        ("Thresholds", "In excess of ₦5,000,000 (individual) and ₦10,000,000 (body corporate), single transaction"),
        ("Transactions reviewed", str(p.ctx["scanned"])),
        ("Reportable transactions", f"{len(rows)} with a total value of ₦{naira(total)}"),
    ])
    if rows:
        d.table(["Date", "File by", "Customer", "Type", "Account", "BVN / RC", "Transaction", "Amount (₦)", "Branch"],
                [[r["t"].date.isoformat(), r["deadline"].isoformat() + (" (late)" if r["late"] else ""), r["t"].customer_name, r["t"].customer_type, r["t"].account_number, r["t"].bvn_or_rc, r["t"].transaction_type, naira(r["t"].amount), r["t"].branch] for r in rows]
                + [["Total", "", "", "", "", "", "", naira(total), ""]],
                numeric_cols=(7,), bold_last=True, font_size=8)
    else:
        d.para("No single transaction in the period exceeded the statutory thresholds; no currency transaction report is required for the period.")
    late = sum(1 for r in rows if r["late"])
    statement = "I confirm that the transactions above have been extracted from the institution's records for the period stated and filed on goAML"
    if late:
        statement += f". {late} transaction(s) marked (late) were identified after the seven-day window and have been filed without further delay."
    else:
        statement += " within seven days of each transaction."
    d.para(statement)
    d.signatures([(p.data["reporting_officer"], "Reporting Officer"), _cco(p)])
    sheet = ("CTR schedule", ["Transaction date", "File by", "Late", "Customer name", "Customer type", "Account number", "BVN / RC", "Transaction type", "Amount (NGN)", "Narration", "Branch", "Channel", "Source row"],
             [[r["t"].date, r["deadline"], "Y" if r["late"] else "N", r["t"].customer_name, r["t"].customer_type, r["t"].account_number, r["t"].bvn_or_rc, r["t"].transaction_type, float(r["t"].amount), r["t"].narration, r["t"].branch, r["t"].channel, r["t"].row] for r in rows])
    return [(_filename(p, "docx"), d.to_bytes(), DOCX), (_filename(p, "xlsx"), _xlsx([sheet]), XLSX)]


# ─── NDIC certified deposits ──────────────────────────────────────────────────

NDIC_PREMIUM_CEILING = 0.5 / 100  # 8/16 of one per cent


def _compute_ndic(p: Prepared, upload: bytes | None) -> None:
    x = p.data
    total = sum(x.get(k) or 0 for k in ("demand_deposits", "savings_deposits", "time_deposits", "other_deposits"))
    excluded = (x["insider_deposits"] or 0) + (x["collateral_deposits"] or 0)
    if excluded > total:
        p.errors.append("Excluded deposits exceed total deposit liabilities.")
        return
    assessable = total - excluded
    if x["auditor_certificate_date"] and p.period and x["auditor_certificate_date"] <= p.period.end:
        p.warnings.append("The auditor's certificate is dated on or before 31 December; it should certify the year-end balances after the year end.")
    p.ctx.update(total=total, excluded=excluded, assessable=assessable, premium=assessable * NDIC_PREMIUM_CEILING)
    p.figures = [("Total deposits", f"₦{naira(total)}"), ("Exclusions", f"₦{naira(excluded)}"), ("Assessable deposits", f"₦{naira(assessable)}"),
                 ("Premium at statutory ceiling", f"₦{naira(assessable * NDIC_PREMIUM_CEILING)}")]


def _render_ndic(p: Prepared) -> list[tuple[str, bytes, str]]:
    x, c, inst = p.data, p.ctx, p.profile["institution_name"]
    d = _doc(p)
    d.letter_opening(p.letter_date, p.spec.recipient, f"Submission of Certified Deposit Liabilities as at {_period_end_text(p)}")
    d.para(f"In compliance with Section 17 of the Nigeria Deposit Insurance Corporation Act 2023, we hereby forward the total deposit liabilities of {inst} as at {_period_end_text(p)}, certified by our approved auditors, {x['auditor_name']}, by a certificate dated {long_date(x['auditor_certificate_date'])}.")
    d.table(["Deposit liabilities as at " + _period_end_text(p), "₦"], [
        ["Demand deposits", naira(x["demand_deposits"])],
        ["Savings deposits", naira(x["savings_deposits"])],
        ["Time / term deposits", naira(x["time_deposits"])],
        ["Other deposits", naira(x.get("other_deposits") or 0, dash_zero=True)],
        ["Total deposit liabilities", naira(c["total"])],
        ["Less: insider deposits (staff and directors)", f"({naira(x['insider_deposits'])})"],
        ["Less: deposits held as collateral against loans", f"({naira(x['collateral_deposits'])})"],
        ["Assessable deposit liabilities", naira(c["assessable"])],
    ], widths_cm=(11.5, 5), numeric_cols=(1,), bold_last=True, bold_rows=[4])
    d.para(f"At the statutory ceiling of 8/16 of one per cent for deposit-taking financial institutions, the premium on the assessable base would not exceed ₦{naira(c['premium'])}. We await the Corporation's demand notice and will remit the premium within the period stated in it.")
    d.para("Kindly acknowledge receipt.")
    d.closing([_md(p), _cfo(p)], enclosures=[f"Auditor's certificate on deposit liabilities ({x['auditor_name']})"], cc=p.spec.cc)
    return [(_filename(p, "docx"), d.to_bytes(), DOCX)]


# ─── Audited financial statements ─────────────────────────────────────────────


def _compute_afs(p: Prepared, upload: bytes | None) -> None:
    x = p.data
    if x["audit_report_date"] and x["board_approval_date"] and x["audit_report_date"] < x["board_approval_date"]:
        p.warnings.append("The auditor's report is dated before the Board approved the accounts; the auditor normally signs on or after Board approval.")
    p.figures = [("Total assets", f"₦{naira(x['total_assets'])}"), ("Profit before tax", f"₦{naira(x['profit_before_tax'])}"), ("Shareholders' funds", f"₦{naira(x['shareholders_funds'])}")]
    if p.ctx.get("due"):
        p.figures.append(("Due", long_date(p.ctx["due"])))


def _render_afs(p: Prepared) -> list[tuple[str, bytes, str]]:
    x, inst = p.data, p.profile["institution_name"]
    d = _doc(p)
    d.letter_opening(p.letter_date, p.spec.recipient, f"Submission of Audited Financial Statements for the Year Ended {_period_end_text(p)} for Approval")
    d.para(f"We hereby submit the audited financial statements of {inst} for the year ended {_period_end_text(p)}, together with the abridged version proposed for publication, for the approval of the Central Bank of Nigeria.")
    d.para(f"The financial statements were approved by the Board of Directors on {long_date(x['board_approval_date'])} and audited by {x['auditor_name']}, whose report is dated {long_date(x['audit_report_date'])}.")
    rows = [["Total assets", naira(x["total_assets"])], ["Profit / (loss) before tax", naira(x["profit_before_tax"])], ["Shareholders' funds", naira(x["shareholders_funds"])]]
    if x.get("proposed_dividend"):
        rows.append(["Proposed dividend", naira(x["proposed_dividend"])])
    d.table(["Key figures — year ended " + _period_end_text(p), "₦"], rows, widths_cm=(11.5, 5), numeric_cols=(1,))
    d.para("The Bank will not publish the financial statements, or any abridged version of them, until the approval of the Central Bank of Nigeria has been obtained. Kindly acknowledge receipt.")
    enclosures = [
        "Audited financial statements, signed by the directors and the external auditor",
        "Abridged financial statements proposed for publication",
        "Extract of the Board resolution approving the financial statements",
    ]
    if x["management_letter_enclosed"]:
        enclosures.append("External auditor's management letter and management's responses")
    d.closing([_md(p), _cfo(p)], enclosures=enclosures)
    return [(_filename(p, "docx"), d.to_bytes(), DOCX)]


# ─── NDPC compliance audit ────────────────────────────────────────────────────


def _compute_ndpc(p: Prepared, upload: bytes | None) -> None:
    x = p.data
    if (x["breaches_notified_72h"] or 0) > (x["breaches"] or 0):
        p.errors.append("Breaches notified within 72 hours cannot exceed the number of breaches.")
    elif (x["breaches_notified_72h"] or 0) < (x["breaches"] or 0):
        p.warnings.append("Not every breach was notified within 72 hours; the report must explain each late or omitted notification.")
    if (x["dsr_resolved"] or 0) > (x["dsr_received"] or 0):
        p.errors.append("Data-subject requests resolved cannot exceed requests received.")
    if not x.get("privacy_policy_url"):
        p.warnings.append("No privacy policy URL supplied; a published privacy notice is expected.")
    p.figures = [("Data subjects", f"{int(x['data_subjects'] or 0):,}"), ("DPIAs", str(int(x["dpias_conducted"] or 0))),
                 ("Breaches / notified in 72h", f"{int(x['breaches'] or 0)} / {int(x['breaches_notified_72h'] or 0)}"),
                 ("DSRs received / resolved", f"{int(x['dsr_received'] or 0)} / {int(x['dsr_resolved'] or 0)}")]


def _render_ndpc(p: Prepared) -> list[tuple[str, bytes, str]]:
    x, inst = p.data, p.profile["institution_name"]
    year = p.period.end.year
    d = _doc(p)
    d.letter_opening(p.letter_date, p.spec.recipient, f"Data Protection Compliance Audit Return for the Year Ended 31st December, {year}")
    d.para(f"In compliance with the Nigeria Data Protection Act 2023 and the General Application and Implementation Directive, {inst} hereby files its Data Protection Compliance Audit Return for the year ended 31st December, {year}, through its licensed Data Protection Compliance Organisation, {x['dpco_name']}.")
    d.para("The Bank's data-protection position for the year is summarised in the attached report. Kindly acknowledge receipt.")
    d.closing([_md(p), (x["dpo_name"], "Data Protection Officer")], enclosures=["Data protection compliance report", f"Audit report of {x['dpco_name']}"])
    d.page_break()
    d.heading(f"Data protection compliance report — year ended 31 December {year}")
    d.heading("1. Organisation", 2)
    d.key_values([("Data controller", inst), ("Address", p.profile.get("head_office_address") or ""), ("Data Protection Officer", x["dpo_name"]),
                  ("DPCO", x["dpco_name"]), ("Privacy policy", x.get("privacy_policy_url") or "")])
    d.heading("2. Processing", 2)
    d.key_values([("Approximate number of data subjects", f"{int(x['data_subjects'] or 0):,}"), ("Categories of personal data", x["data_categories"]), ("Lawful bases relied on", x["lawful_bases"])])
    d.heading("3. Accountability and risk", 2)
    d.key_values([("Data protection impact assessments conducted", str(int(x["dpias_conducted"] or 0))),
                  ("Personal data breaches", str(int(x["breaches"] or 0))),
                  ("Breaches notified to the NDPC within 72 hours", str(int(x["breaches_notified_72h"] or 0))),
                  ("Data-subject requests received / resolved", f"{int(x['dsr_received'] or 0)} / {int(x['dsr_resolved'] or 0)}")])
    d.heading("4. Transfers and processors", 2)
    d.key_values([("Cross-border transfers and safeguards", x.get("cross_border_transfers") or "None"), ("Data processors and contracts", x.get("processors") or "None")])
    d.heading("5. Security and training", 2)
    d.key_values([("Technical and organisational measures", x["security_measures"]), ("Staff training", x.get("training") or "")])
    d.heading("6. Attestation", 2)
    d.para(f"We confirm that this report fairly states the data-protection practices of {inst} for the year ended 31 December {year}.")
    d.signatures([_md(p), (x["dpo_name"], "Data Protection Officer")])
    return [(_filename(p, "docx"), d.to_bytes(), DOCX)]


_COMPUTE: dict[str, Callable[[Prepared, bytes | None], None]] = {
    "cbn-monthly-prudential": _compute_prudential,
    "cbn-fraud-forgeries": _compute_fraud,
    "cbn-cg-compliance": _compute_cg,
    "cbn-whistleblowing": _compute_wb,
    "nfiu-str": _compute_str,
    "nfiu-ctr": _compute_ctr,
    "ndic-deposit-certification": _compute_ndic,
    "cbn-afs-submission": _compute_afs,
    "ndpc-compliance-audit": _compute_ndpc,
}
_RENDER: dict[str, Callable[[Prepared], list[tuple[str, bytes, str]]]] = {
    "cbn-monthly-prudential": _render_prudential,
    "cbn-fraud-forgeries": _render_fraud,
    "cbn-cg-compliance": _render_cg,
    "cbn-whistleblowing": _render_wb,
    "nfiu-str": _render_str,
    "nfiu-ctr": _render_ctr,
    "ndic-deposit-certification": _render_ndic,
    "cbn-afs-submission": _render_afs,
    "ndpc-compliance-audit": _render_ndpc,
}
